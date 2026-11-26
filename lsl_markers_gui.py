# ---------------------------------------------------------------------------
# @file lsl_markers_gui.py
# @brief GUI for sending LSL markers
#
# Provides a simple graphical interface for sending markers via LSL (Lab Streaming Layer).
#encoding for buttons contained in event_markers_config.json.
#
# @author Emily
# @version 1.1
#
# @see event_markers_config.json
# ---------------------------------------------------------------------------

import tkinter as tk
import json

from pylsl import StreamInfo, StreamOutlet
from pathlib import Path

# __ Utility _______________________
import json

def load_json_config(CONFIG_PATH: str) -> dict:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    return config


# ---------- Configuration ----------
ROOT_DIR = Path(__file__).resolve().parents[0]
CONFIG_PATH = ROOT_DIR / "configs" / "event_markers_config.json"

config = load_json_config(CONFIG_PATH)

# convert config info to list of tuples mapping event names to codes
buttons = [(event["name"], event["value"]) for event in config["events"]]

"BUTTONS TO EXCLUDE FROM GUI (for now, can be added back in later if needed)"
exclude_buttons = ["Trial Start", "Trial End", "Scale Reading"]  # example of buttons to exclude

# Filter out excluded buttons
buttons = [(text, code) for text, code in buttons if text not in exclude_buttons]


# ---------- Create LSL outlet ----------
info = StreamInfo(
    name='Event_Markers',
    type='Markers',
    channel_count=1,
    nominal_srate=0,  # irregular sampling
    channel_format='int32',
    source_id='marker_gui_001'
)

outlet = StreamOutlet(info)

# ---------- Marker send function ----------
# def send_marker(code):
#     outlet.push_sample([code])
#     status_label.config(text=f"Last marker sent: {code}")

# ---------- Marker send (label status update) ----------
def send_marker(code, label):
    outlet.push_sample([code])
    status_label.config(text=f"Last marker sent: {label}")


# ---------- GUI setup ----------
root = tk.Tk()
root.title("LSL Marker Sender")
root.geometry("300x350")

# # ---------- Buttons ----------
# buttons = [
#     ("Block Start", 1),
#     ("Block End", 2),
#     ("Trial Start", 10),
#     ("Trial End", 11),
#     ("Scale Reading", 40),
#     ("Manual Event", 50),
# ]

for text, code in buttons:
    btn = tk.Button(
        root,
        text=text,
        font=("Arial", 14),
        height=2,
        command=lambda c=code, t=text: send_marker(c, t)
    )
    btn.pack(fill="x", padx=20, pady=5)

# ---------- Status label ----------
status_label = tk.Label(
    root,
    text="No marker sent yet",
    font=("Arial", 12)
)
status_label.pack(pady=15)

# ---------- Run GUI ----------
root.mainloop()
