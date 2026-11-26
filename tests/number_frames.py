#!/usr/bin/env python3
"""
Add frame number overlay to an MP4 file.
Output is saved as <original_name>-numbered.mp4

Usage:
    python add_frame_numbers.py <input.mp4>

Requirements:
    pip install opencv-python
"""

import cv2
import sys
from pathlib import Path


def add_frame_numbers(input_path: str) -> None:
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    output_file = input_file.with_name(f"{input_file.stem}-numbered{input_file.suffix}")

    cap = cv2.VideoCapture(str(input_file))
    if not cap.isOpened():
        print(f"Error: Could not open video: {input_path}")
        sys.exit(1)

    fps        = cap.get(cv2.CAP_PROP_FPS)
    width      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total      = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fourcc     = cv2.VideoWriter_fourcc(*"mp4v")

    out = cv2.VideoWriter(str(output_file), fourcc, fps, (width, height))

    # ── overlay style ──────────────────────────────────────────────────────────
    font       = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, width / 1280)          # scales with resolution
    thickness  = max(1, int(font_scale * 2))
    padding    = int(10 * font_scale)
    text_color = (255, 255, 255)                  # white text
    shadow_color = (0, 0, 0)                      # black shadow for readability
    # ──────────────────────────────────────────────────────────────────────────

    frame_num = 0
    print(f"Processing {total} frames → {output_file.name}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        label = f"Frame: {frame_num}"
        (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

        x = padding
        y = th + padding

        # drop-shadow for contrast on any background
        cv2.putText(frame, label, (x + 2, y + 2), font, font_scale, shadow_color, thickness + 1, cv2.LINE_AA)
        cv2.putText(frame, label, (x,     y    ), font, font_scale, text_color,   thickness,     cv2.LINE_AA)

        out.write(frame)
        frame_num += 1

        if frame_num % 100 == 0:
            print(f"  {frame_num}/{total} frames done…")

    cap.release()
    out.release()
    print(f"\nDone! Saved to: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python add_frame_numbers.py <input.mp4>")
        sys.exit(1)

    add_frame_numbers(sys.argv[1])