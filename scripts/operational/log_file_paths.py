import os
import csv
import argparse

def log_file_paths_to_csv(folder_path, output_csv="file_paths.csv"):
    file_paths = []

    # Recursively walk through the folder
    for root, _, files in os.walk(folder_path):
        for file in files:
            full_path = os.path.join(root, file)
            file_paths.append(full_path)

    # Write to CSV
    with open(output_csv, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['file_path'])
        for path in file_paths:
            writer.writerow([path])

    print(f"File paths written to {output_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log all file paths in a folder to a CSV.")
    parser.add_argument("folder_path", help="Path to the folder to traverse.")
    parser.add_argument("--output", help="Path to the output CSV file (default: file_paths.csv)", default="file_paths.csv")
    args = parser.parse_args()

    log_file_paths_to_csv(args.folder_path, args.output)
