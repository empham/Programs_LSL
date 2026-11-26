# XDF Viewer v1.2

import pyxdf
import os
import numpy as np
import matplotlib.pyplot as plt

# -----------------------------
# Get XDF path from user
# -----------------------------
user_input = input("Enter the full path to the XDF file: ").strip().strip('"').strip("'")

xdf_path = os.path.expanduser(user_input)
xdf_path = os.path.normpath(xdf_path)

if not os.path.isfile(xdf_path):
    raise FileNotFoundError(f"The file does not exist: {xdf_path}")

print(f"\nUsing XDF file: {xdf_path}")

# -----------------------------
# Load XDF
# -----------------------------
streams, header = pyxdf.load_xdf(xdf_path)

# -----------------------------
# List streams
# -----------------------------
print("\nStreams in file:")
for i, s in enumerate(streams):
    name = s['info']['name'][0]
    stype = s['info']['type'][0] if 'type' in s['info'] else "unknown"
    print(f"{i}: {name} (type: {stype})")

# -----------------------------
# Helper function:
# fix orientation safely
# -----------------------------
def fix_orientation(ts, data):
    arr = np.array(data)

    if arr.shape[0] != len(ts):
        arr = arr.T

    return arr


# =========================================================
# INDIVIDUAL STREAM PLOTS
# =========================================================
print("\nPlotting individual streams...")

for s in streams:

    name = s['info']['name'][0]
    ts = np.array(s['time_stamps'])
    data_arr = np.array(s['time_series'])

    # Skip non-numeric streams completely
    if not np.issubdtype(data_arr.dtype, np.number):
        continue

    data_arr = fix_orientation(ts, data_arr)

    plt.figure()
    plt.title(name)
    plt.xlabel("Time (s)")
    plt.ylabel("Value")

    # --- Marker streams: single-channel numeric ---
    if data_arr.ndim == 1 or (data_arr.ndim == 2 and data_arr.shape[1] == 1):
        plt.scatter(ts, data_arr.flatten(), s=15)

    # --- Continuous multi-channel streams ---
    else:
        plt.plot(ts, data_arr)

    plt.tight_layout()
    plt.show()

# =========================================================
# FINAL COMBINED PLOT (SYNC LINES + TPS SCALING)
# =========================================================
print("Plotting combined view...")

plt.figure(figsize=(12, 6))
plt.title("All Numeric Streams Combined")
plt.xlabel("Time (s)")
plt.ylabel("Value")

SCALING_SIGNALS = []   # used to determine Y limits

for s in streams:

    name = s['info']['name'][0]
    ts = np.array(s['time_stamps'])
    data_arr = np.array(s['time_series'])

    if not np.issubdtype(data_arr.dtype, np.number):
        continue

    data_arr = fix_orientation(ts, data_arr)

    # -----------------------------
    # SINGLE CHANNEL STREAM
    # -----------------------------
    if data_arr.ndim == 1 or (data_arr.ndim == 2 and data_arr.shape[1] == 1):

        signal = data_arr.flatten()

        # ---- Detect SYNC MARKER ----
        # Few samples relative to duration = marker stream
        if len(signal) < 200:
            for t in ts:
                plt.axvline(t, linestyle="--", alpha=0.5)
            continue

        # ---- Plot normal signal ----
        plt.plot(ts, signal, label=name)
        SCALING_SIGNALS.append(signal)

    # -----------------------------
    # MULTI CHANNEL STREAM
    # -----------------------------
    else:
        for col in range(data_arr.shape[1]):

            signal = data_arr[:, col]

            # ignore dead channels
            if np.max(np.abs(signal)) < 1e-12:
                continue

            plt.plot(ts, signal, label=f"{name}[{col}]")
            SCALING_SIGNALS.append(signal)


# ---------------------------------------------------------
# SET Y LIMITS BASED ON "NORMAL" SIGNALS ONLY
# ---------------------------------------------------------
if SCALING_SIGNALS:

    # Compute reasonable range ignoring huge outliers
    all_vals = np.concatenate(SCALING_SIGNALS)

    # Use percentile instead of max to avoid EMG crushing
    low = np.percentile(all_vals, 0.1)
    high = np.percentile(all_vals, 99.9)

    # add padding so it isn't tight
    padding = (high - low) * 0.15

    plt.ylim(low - padding, high + padding)


plt.legend(fontsize=8, loc="best")
plt.tight_layout()
plt.show()
