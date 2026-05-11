import pandas as pd
import os
tables = [
    "112024",
    "062025_1"
]

for table_name in tables:
    filepath = f"masking_logs/{table_name}.csv"

    if not os.path.exists(filepath):
        print(f"[x] File not found: {filepath}")
        continue

    try:
        df = pd.read_csv(filepath)

        unique_file_paths = df['file_path'].nunique()
        total_rows = df.shape[0]
        applications = df['file_path'].str.split('/').str[-3].nunique()

        print(f"\n================ Results for {table_name} =================")
        print(f"Total pages processed: {total_rows}")
        print(f"Number of unique file paths: {unique_file_paths}")
        print(f"Number of applications processed: {applications}")

    except Exception as e:
        print(f"[x] Failed to process {filepath}: {e}")
