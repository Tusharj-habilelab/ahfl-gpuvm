# Community 22: get_all_files_recursive()

**Members:** 7

## Nodes

- **count_total_applications** (`scripts_operational_count_total_applications_py`, File, degree: 6)
- **clean_string()** (`scripts_operational_count_total_applications_py_clean_string`, Function, degree: 2)
- **extract_application_info()** (`scripts_operational_count_total_applications_py_extract_application_info`, Function, degree: 2)
- **get_all_files_recursive()** (`scripts_operational_count_total_applications_py_get_all_files_recursive`, Function, degree: 1)
- **os** (`scripts_operational_count_total_applications_py_import_os`, Module, degree: 1)
- **pandas** (`scripts_operational_count_total_applications_py_import_pandas`, Module, degree: 1)
- **sys** (`scripts_operational_count_total_applications_py_import_sys`, Module, degree: 1)

## Relationships

- scripts_operational_count_total_applications_py → scripts_operational_count_total_applications_py_import_os (imports)
- scripts_operational_count_total_applications_py → scripts_operational_count_total_applications_py_import_sys (imports)
- scripts_operational_count_total_applications_py → scripts_operational_count_total_applications_py_import_pandas (imports)
- scripts_operational_count_total_applications_py → scripts_operational_count_total_applications_py_get_all_files_recursive (defines)
- scripts_operational_count_total_applications_py → scripts_operational_count_total_applications_py_clean_string (defines)
- scripts_operational_count_total_applications_py → scripts_operational_count_total_applications_py_extract_application_info (defines)
- scripts_operational_count_total_applications_py_extract_application_info → scripts_operational_count_total_applications_py_clean_string (calls)

