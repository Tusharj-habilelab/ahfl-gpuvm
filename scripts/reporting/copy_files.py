import shutil
import pandas as pd
import os

count = 0
error_count = 0

file_paths_df = pd.read_csv('file_paths.csv')

for index, row in file_paths_df.iterrows():
    source = row['source']
    destination = row['destination']

    try:
        dest_dir = os.path.dirname(destination)
        os.makedirs(dest_dir, exist_ok=True)

        shutil.move(source, destination)
        count += 1
    except Exception as e:
        error_count += 1
        print(f"Error copying {source} to {destination}: {e}")
    
    if count % 50 == 0 and count > 0:
        print(f"Copied {count} files so far...")

print(f"Total files copied: {count}")
print(f"Total errors encountered: {error_count}")
