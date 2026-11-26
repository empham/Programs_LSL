"""
camera_daq.py — Video capture DAQ with LSL frame sync.

Config files (JSON):
  camera_config.json  — camera settings
  data_config.json    — base data directory

Output: <base_dir>/Raw/camera/camera_YYYYMMDD_HHMMSS.mp4
"""

import cv2
import os
import sys
import signal
import argparse
import threading
import csv
from datetime import datetime
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream, resolve_byprop

# __ Utility _______________________
import json

def load_json_config(CONFIG_PATH: str) -> dict:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    return config

# ── LSL setup ─────────────────────────────────────────────────────────────────

def create_lsl_outlet(stream_name: str = "CameraFrameIndex") -> StreamOutlet:
    info = StreamInfo(
        name=stream_name,
        type="Markers",
        channel_count=1,
        nominal_srate=0,          # irregular rate — push on each frame
        channel_format="int32",
        source_id="camera_daq_01",
    )
    return StreamOutlet(info)

# ── LSL inlet (sync marker) ────────────────────────────────────────────────────
 
def resolve_marker_inlet(stream_name: str, timeout: float = 5.0):
    """
    Resolve a named LSL stream and return an inlet, or None if not found.
    Resolution is attempted once at startup; if the stream isn't up yet the
    audit feature is skipped rather than blocking the recording.
    """
    print(f"[INFO] Looking for sync-marker stream '{stream_name}' (timeout {timeout}s)…")
    streams = resolve_byprop("name", stream_name, timeout=timeout)
    if not streams:
        print(f"[WARN] Sync-marker stream '{stream_name}' not found — buffer auditing disabled.")
        return None
    inlet = StreamInlet(streams[0], max_buflen=360)
    print(f"[INFO] Connected to sync-marker stream '{stream_name}'.")
    return inlet

# ── Output path ───────────────────────────────────────────────────────────────

def build_output_path(data_dir: str) -> str:
    out_dir = os.path.join(data_dir, "Raw", "camera")
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(out_dir, f"camera_{timestamp}.mp4")

# ── Frame overlay ─────────────────────────────────────────────────────────────

FONT       = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.7
THICKNESS  = 2
PADDING    = 8

def draw_frame_number(frame, frame_no: int):
    """Burn frame number into top-left corner (white text, black shadow)."""
    text = f"Frame: {frame_no}"
    origin = (PADDING, PADDING + 20)
    # Shadow
    cv2.putText(frame, text, (origin[0] + 1, origin[1] + 1),
                FONT, FONT_SCALE, (0, 0, 0), THICKNESS + 1, cv2.LINE_AA)
    # Text
    cv2.putText(frame, text, origin,
                FONT, FONT_SCALE, (255, 255, 255), THICKNESS, cv2.LINE_AA)
    return frame

def draw_flash(frame, flash_frames_left: int, total_flash: int):
    """
    Bright white rectangle in the top-right corner.
    Fades out linearly over the flash duration so it's easy to find the
    first frame via a brightness threshold in the analyzer.
    """
    h, w = frame.shape[:2]
    box_w, box_h = 80, 80
    x1, y1 = w - box_w - PADDING, PADDING
    x2, y2 = w - PADDING,         PADDING + box_h
    alpha = flash_frames_left / total_flash          # 1.0 → 0.0
    color = (int(255 * alpha),) * 3                  # white → black
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0,0,0), 1)
    return frame
 
 
def flash_corner_roi(frame):
    """Return the mean brightness of the flash ROI (used by analyzer)."""
    h, w = frame.shape[:2]
    box_w, box_h = 80, 80
    x1 = w - box_w - PADDING
    y1 = PADDING
    roi = frame[y1:y1+box_h, x1:x1+box_w]
    return float(cv2.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY))[0])
 
# ── Marker polling thread ──────────────────────────────────────────────────────
 
class MarkerPoller(threading.Thread):
    """
    Polls the sync-marker LSL inlet in a background thread so the main capture
    loop never blocks waiting for samples.
    """
    def __init__(self, inlet: StreamInlet):
        super().__init__(daemon=True)
        self.inlet    = inlet
        self._lock    = threading.Lock()
        self._pending = []      # list of (marker_value, lsl_timestamp)
        self._running = True
 
    def run(self):
        while self._running:
            sample, ts = self.inlet.pull_sample(timeout=0.005)
            if sample is not None:
                with self._lock:
                    self._pending.append((sample[0], ts))
 
    def drain(self):
        """Return and clear any markers received since last call."""
        with self._lock:
            out, self._pending = self._pending, []
        return out
 
    def stop(self):
        self._running = False

# ── Main capture loop ─────────────────────────────────────────────────────────

def run(camera_cfg_path: str, data_cfg_path: str):
    camera_cfg = load_json_config(camera_cfg_path)
    data_cfg   = load_json_config(data_cfg_path)

    device_index    = camera_cfg.get("device_index", 0)
    fps             = camera_cfg.get("fps", 15)
    width           = camera_cfg.get("width", 800)
    height          = camera_cfg.get("height", 600)
    codec           = camera_cfg.get("codec", "mp4v")
    lsl_stream_name = camera_cfg.get("lsl_stream_name", "CameraFrameIndex")
    data_dir        = data_cfg["external_paths"]["data_dir"]

    event_stream_name   = camera_cfg.get("event_marker_stream_name", "Event_Markers")
    event_id_no         = camera_cfg.get("event_marker_id_for_flash", 999)
    flash_dur           = camera_cfg.get("flash_duration_frames", fps)

    ## Initialize camera
    cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera at device index {device_index}.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS,          fps)

    # Re-read actual values after setting (camera may clamp them)
    actual_w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS) or fps

    out_path  = build_output_path(data_dir)
    fourcc    = cv2.VideoWriter_fourcc(*codec)
    writer    = cv2.VideoWriter(out_path, fourcc, actual_fps, (actual_w, actual_h))

    if not writer.isOpened():
        print(f"[ERROR] Cannot open VideoWriter for {out_path}.")
        cap.release()
        sys.exit(1)
    
    print(f"[INFO] Camera initialized → {actual_w}x{actual_h} @ {actual_fps:.1f} fps")
    print(f"[INFO] VideoWriter opened → {out_path}")

    ## Initialize LSL outlet and inlet (for sync markers)
    outlet    = create_lsl_outlet(lsl_stream_name)
    frame_no  = 0

    flash_frames_left = 0
    poller = None
    sync_events = [] #[(marker_value, lsl_timestamp, frame_no_at_receipt)]
    audit_mode = bool(event_stream_name)

    if audit_mode:
        inlet = resolve_marker_inlet(event_stream_name)
        if inlet is None:
            audit_mode = False
            print("[WARN] Sync-marker stream not found — buffer auditing disabled.")
        else:
            poller = MarkerPoller(inlet)
            poller.start()
            print("[INFO] Sync-marker polling thread started.")


    ## Main capture loop
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        print("\n[INFO] Interrupt received — stopping capture.")
        running = False

    signal.signal(signal.SIGINT,  handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"[INFO] Recording → {out_path}")
    print(f"[INFO] Resolution: {actual_w}x{actual_h} @ {actual_fps:.1f} fps")
    if audit_mode:
        print(f"[INFO] Buffer audit enabled (flash = {flash_dur} frames)")
    print("[INFO] Press Ctrl+C to stop.\n")

    while running:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Frame capture failed — stopping.")
            break

        # 1. Push frame index to LSL
        outlet.push_sample([frame_no])

        # 2. Check for sync markers and flash if any received
        if audit_mode and poller:
            for marker_val, marker_ts in poller.drain():
                if marker_val == event_id_no:
                    sync_events.append((marker_val, marker_ts, frame_no))
                    flash_frames_left = flash_dur
                    print(f"[SYNC] Marker '{marker_val}' at LSL t={marker_ts:.4f}  frame={frame_no}")

        # 3. Overlay frame number and write to file
        draw_frame_number(frame, frame_no)
        if flash_frames_left > 0:
            draw_flash(frame, flash_frames_left, flash_dur)
            flash_frames_left -= 1
        
        # 4. Write frame to video file
        writer.write(frame)

        # 5. Display frame (optional)
        cv2.imshow("Camera DAQ", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[INFO] 'q' pressed — stopping capture.")
            break

        frame_no += 1

        # Optional: print a heartbeat every 300 frames
        if frame_no % 300 == 0:
            print(f"[INFO] {frame_no} frames captured.")

    ## Shutdown procedures
    if poller:
        poller.stop()
        print("[INFO] Sync-marker polling thread stopped.")
    
    cap.release()
    writer.release()

    # Write sync events to a CSV file for later analysis
    if audit_mode and sync_events:
        csv_path = out_path.replace(".mp4", "_sync_events.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["marker_value", "lsl_timestamp", "frame_no"])
            for marker_val, marker_ts, frame_no_at_receipt in sync_events:
                f.write(f"{marker_val},{marker_ts:.6f},{frame_no_at_receipt}\n")
        print(f"[INFO] Sync events → {csv_path}")
    print(f"\n[INFO] Done. {frame_no} frames saved to:\n       {out_path}")

# ── Post-hoc buffer analyzer ──────────────────────────────────────────────────
 
FLASH_BRIGHTNESS_THRESHOLD = 180   # 0–255; tune if lighting conditions vary
 
def analyze(stem: str):
    """
    For each sync event, scan the video forward from the receipt frame to find
    the first frame where the flash ROI exceeds FLASH_BRIGHTNESS_THRESHOLD.
    The difference between that frame's LSL timestamp and the marker's LSL
    timestamp is the estimated buffer lag.
    """
    video_path       = stem + ".mp4"
    sync_events_path = stem + "_sync_events.csv"
    report_path      = stem + "_buffer_report.csv"
 
    for p in (video_path, sync_events_path):
        if not os.path.exists(p):
            print(f"[ERROR] Missing file: {p}")
            sys.exit(1)
 

 
    # Load sync events
    sync_events = []
    with open(sync_events_path, newline="") as f:
        for row in csv.DictReader(f, delimiter=","):
            sync_events.append({
                "marker_value":       row["marker_value"],
                "marker_lsl_ts":      float(row["lsl_timestamp"]),
                "frame_no_at_receipt": int(row["frame_no"]),
            })
 
    if not sync_events:
        print("[INFO] No sync events found — nothing to analyze.")
        return
 
    cap        = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    results    = []
 
    for ev in sync_events:
        receipt_frame = ev["frame_no_at_receipt"]
        # Scan from a few frames before receipt in case of sub-frame timing
        scan_start = max(0, receipt_frame - 3)
        cap.set(cv2.CAP_PROP_POS_FRAMES, scan_start)
 
        flash_frame = None
        for fn in range(scan_start, min(scan_start + 60, total_frames)):
            ret, frame = cap.read()
            if not ret:
                break
            brightness = flash_corner_roi(frame)
            if brightness >= FLASH_BRIGHTNESS_THRESHOLD:
                flash_frame = fn
                break
 
        if flash_frame is None:
            print(f"[WARN] Flash not detected for marker '{ev['marker_value']}' "
                  f"(receipt frame {receipt_frame}) — threshold may need adjustment.")
            results.append({**ev, "flash_frame": None, "lag_frames": None, "lag_seconds": None})
            continue
 
        # Print flash frame no and ask user to input flash LSL timestamp (from LSL recording)
        print(f"Flash detected for marker '{ev['marker_value']}' at frame {flash_frame}. Please input the corresponding LSL timestamp:")
        flash_lsl_ts  = float(input().strip())
        lag_seconds   = (flash_lsl_ts - ev["marker_lsl_ts"]) if flash_lsl_ts else None
        lag_frames    = flash_frame - receipt_frame
 
        results.append({
            **ev,
            "flash_frame":  flash_frame,
            "flash_lsl_ts": flash_lsl_ts,
            "lag_frames":   lag_frames,
            "lag_seconds":  lag_seconds,
        })
 
        sign = "+" if lag_frames >= 0 else ""
        print(f"[RESULT] Marker '{ev['marker_value']}': "
              f"receipt frame={receipt_frame}, flash frame={flash_frame}, "
              f"lag={sign}{lag_frames} frames / {sign}{lag_seconds:.4f}s")
 
    cap.release()
 
    # Write report
    with open(report_path, "w", newline="") as f:
        w = csv.writer(f, delimiter=",")
        w.writerow(["marker_value", "marker_lsl_ts", "frame_no_at_receipt",
                    "flash_frame", "flash_lsl_ts", "lag_frames", "lag_seconds"])
        for r in results:
            w.writerow([
                r["marker_value"],
                f"{r['marker_lsl_ts']:.6f}",
                r["frame_no_at_receipt"],
                r.get("flash_frame", ""),
                f"{r['flash_lsl_ts']:.6f}" if r.get("flash_lsl_ts") else "",
                r.get("lag_frames", ""),
                f"{r['lag_seconds']:.6f}" if r.get("lag_seconds") is not None else "",
            ])
 
    valid = [r for r in results if r.get("lag_seconds") is not None]
    if valid:
        lags = [r["lag_seconds"] for r in valid]
        print(f"\n[SUMMARY] {len(valid)}/{len(results)} markers detected")
        print(f"          Mean lag : {sum(lags)/len(lags)*1000:.1f} ms")
        print(f"          Min  lag : {min(lags)*1000:.1f} ms")
        print(f"          Max  lag : {max(lags)*1000:.1f} ms")
 
    print(f"\n[INFO] Report → {report_path}")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Camera DAQ with LSL frame sync and buffer-lag auditing.")
    parser.add_argument(
        "--camera-config",
        default=".\\configs\\camera_config.json",
        help="Path to camera config JSON (default: camera_config.json)",
    )
    parser.add_argument(
        "--paths-config",
        default=".\\configs\\external_paths.json",
        help="Path to data config JSON (default: external_paths.json)",
    )
    parser.add_argument(
        "--analyze", metavar="STEM",
        help="Post-hoc buffer analysis. Pass the file stem printed at end of recording "
             "(e.g. /data/Raw/camera/camera_20260622_143501).",
    )
    args = parser.parse_args()
    if args.analyze:
        analyze(args.analyze)
    else:
        run(args.camera_config, args.paths_config)