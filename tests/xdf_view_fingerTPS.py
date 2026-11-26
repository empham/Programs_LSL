import pyxdf
import os
import matplotlib.pyplot as plt

import os

# Ask user for path
user_input = input("Enter the full path to the XDF file: ").strip().strip('"').strip("'")

# Expand ~ and normalize path
xdf_path = os.path.expanduser(user_input)
xdf_path = os.path.normpath(xdf_path)

# Check existence
if not os.path.isfile(xdf_path):
    raise FileNotFoundError(f"The file does not exist: {xdf_path}")

print(f"Using XDF file: {xdf_path}")

streams, header = pyxdf.load_xdf(xdf_path)

# List all streams found
print("Streams in file:")
for s in streams:
    print(" -", s['info']['name'][0])

# --- Plot FingerTPS force data ---
f = next(s for s in streams if s['info']['name'][0] == 'FingerTPS')

data = f['time_series']        # shape: samples x channels OR channels x samples (handled below)
ts = f['time_stamps']

# Ensure correct orientation
if data.shape[0] != len(ts):
    data = data.T

plt.figure()
plt.plot(ts, data)
plt.xlabel("Time (s)")
plt.ylabel("Force")
plt.title("FingerTPS Force")
plt.tight_layout()
plt.show()

# --- Plot Trigger stream ---
t = next(s for s in streams if s['info']['name'][0] == 'Stimulus PC')

trig = t['time_series']
tts = t['time_stamps']

plt.figure()
plt.stem(tts, trig)
plt.xlabel("Time (s)")
plt.ylabel("Trigger value")
plt.title("Trigger Events")
plt.tight_layout()
plt.show()