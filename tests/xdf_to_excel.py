import pyxdf
import pandas as pd
import numpy as np
import os
import json

xdf_path = input("Enter full path to XDF file: ").strip().strip('"').strip("'")
xdf_path = os.path.expanduser(xdf_path)

if not os.path.isfile(xdf_path):
    raise FileNotFoundError("File not found.")

print("Loading XDF...")
streams, header = pyxdf.load_xdf(xdf_path)

output_file = os.path.splitext(xdf_path)[0] + "_RAW.xlsx"

print("Writing to Excel...")

with pd.ExcelWriter(output_file) as writer:

    # -------- Save global header ----------
    header_df = pd.DataFrame({
        "key": list(header.keys()),
        "value": [json.dumps(v) for v in header.values()]
    })
    header_df.to_excel(writer, sheet_name="XDF_Header", index=False)

    # -------- Save each stream ----------
    for i, s in enumerate(streams):

        name = s['info']['name'][0] if 'name' in s['info'] else f"Stream{i}"
        sheet_name = f"{i}_{name}"[:31]  # Excel limit

        timestamps = np.array(s['time_stamps'])
        data = np.array(s['time_series'], dtype=object)

        # Convert to DataFrame WITHOUT altering structure
        df = pd.DataFrame(data)

        # Insert timestamps as first column
        if len(timestamps) > 0:
            df.insert(0, "time_stamps", timestamps)

        df.to_excel(writer, sheet_name=sheet_name, index=False)

        # -------- Save metadata ----------
        meta_sheet = f"{sheet_name}_info"[:31]

        meta_flat = {}
        for k, v in s['info'].items():
            meta_flat[k] = json.dumps(v)

        meta_df = pd.DataFrame(meta_flat.items(), columns=["field", "value"])
        meta_df.to_excel(writer, sheet_name=meta_sheet, index=False)

        # -------- Give status update ----------
        print(f"Saved stream '{name}' to sheet '{sheet_name}' with metadata in '{meta_sheet}'")

print("DONE")
print("Saved to:", output_file)
