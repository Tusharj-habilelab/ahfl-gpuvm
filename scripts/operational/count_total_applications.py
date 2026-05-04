import os
import sys
import pandas as pd

def get_all_files_recursive(path):
    file_list = []
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            file_list.append(full_path)
    return file_list

def clean_string(s):
    return s.encode("utf-8", "replace").decode("utf-8")

def extract_application_info(file_list):
    data = []
    application_numbers = set()

    for file_path in file_list:
        try:
            file_path.encode("utf-8")
        except UnicodeEncodeError:
            print("Bad path:", repr(file_path))

        parts = file_path.strip().split(os.sep)
        if len(parts) >= 3:
            app_number = parts[-3]
            application_numbers.add(app_number)
        else:
            app_number = "UNKNOWN"

        data.append({
            "application_number": clean_string(app_number),
            "file_path": clean_string(file_path)
        })

    df = pd.DataFrame(data)
    return df, len(application_numbers)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python count_unique_applications.py <directory_path>")
        sys.exit(1)

    path_to_scan = sys.argv[1]

    if not os.path.isdir(path_to_scan):
        print(f"Error: '{path_to_scan}' is not a valid directory.")
        sys.exit(1)

    folder_name = path_to_scan.split('/')[-1]

    file_list = get_all_files_recursive(path_to_scan)
    print(f"Total unique files found: {len(file_list)}")

    df, app_count = extract_application_info(file_list)
    print(f"Total unique applications found: {app_count}")

    os.makedirs("application_paths", exist_ok=True)
    output_csv = f"application_paths/{folder_name}.csv"
    df.to_csv(output_csv, index=False)
    print(f"CSV written to: {output_csv}")
