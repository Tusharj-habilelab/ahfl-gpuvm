import os
import sys

def get_all_files_recursive(path):
    file_set = set()
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            file_set.add(full_path)
    return file_set, len(file_set)

def count_unique_applications(file_set):
    application_numbers = set()
    for file_path in file_set:
        parts = file_path.strip().split(os.sep)
        if len(parts) >= 3:
            app_number = parts[-3]
            application_numbers.add(app_number)
    return application_numbers, len(application_numbers)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python count_unique_applications.py <directory_path>")
        sys.exit(1)

    path_to_scan = sys.argv[1]

    if not os.path.isdir(path_to_scan):
        print(f"Error: '{path_to_scan}' is not a valid directory.")
        sys.exit(1)

    files, file_count = get_all_files_recursive(path_to_scan)
    print(f"Total unique files found: {file_count}")

    apps, app_count = count_unique_applications(files)
    print(f"Total unique applications found: {app_count}")
