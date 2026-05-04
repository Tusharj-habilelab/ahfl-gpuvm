import os
import shutil
import math
import argparse
from collections import defaultdict

def split_folder_by_applications(src_folder, batches):
    parent_dir = os.path.dirname(src_folder.rstrip("/"))
    base_name = os.path.basename(src_folder.rstrip("/"))

    # Group files by application number
    app_files = defaultdict(list)
    for root, _, files in os.walk(src_folder):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, src_folder)

            # Get application number → 3rd last directory in path
            parts = rel_path.split(os.sep)
            if len(parts) < 3:
                print(f"Skipping file (path too short): {rel_path}")
                continue
            app_number = parts[-3]
            app_files[app_number].append(rel_path)

    applications = list(app_files.keys())
    total_apps = len(applications)
    if total_apps == 0:
        print("No applications found.")
        return

    apps_per_batch = math.ceil(total_apps / batches)

    print(f"Total applications: {total_apps}")
    print(f"Splitting into {batches} batches ({apps_per_batch} applications per batch approx)")

    for i in range(batches):
        batch_folder = os.path.join(parent_dir, f"{base_name}_{i+1}")
        print(f"➡️ Creating batch folder: {batch_folder}")
        os.makedirs(batch_folder, exist_ok=True)

        batch_apps = applications[i*apps_per_batch : (i+1)*apps_per_batch]

        for app_number in batch_apps:
            for rel_path in app_files[app_number]:
                src_path = os.path.join(src_folder, rel_path)
                dest_path = os.path.join(batch_folder, rel_path)

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.move(src_path, dest_path)

        print(f"Batch {i+1} done: {len(batch_apps)} applications moved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split a folder into multiple batches based on application number.")
    parser.add_argument("source_folder", help="Path to the source folder")
    parser.add_argument("num_batches", type=int, help="Number of batches to split into")
    args = parser.parse_args()

    split_folder_by_applications(args.source_folder, args.num_batches)
