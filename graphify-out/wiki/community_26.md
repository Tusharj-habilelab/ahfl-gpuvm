# Community 26: get_failed_paths()

**Members:** 6

## Nodes

- **file_paths** (`services_batch_processor_utils_file_paths_py`, File, degree: 5)
- **get_completed_paths()** (`services_batch_processor_utils_file_paths_py_get_completed_paths`, Function, degree: 1)
- **get_failed_paths()** (`services_batch_processor_utils_file_paths_py_get_failed_paths`, Function, degree: 1)
- **boto3.dynamodb.conditions.Attr** (`services_batch_processor_utils_file_paths_py_import_boto3_dynamodb_conditions_attr`, Module, degree: 1)
- **core.get_dynamo_table** (`services_batch_processor_utils_file_paths_py_import_core_get_dynamo_table`, Module, degree: 1)
- **os** (`services_batch_processor_utils_file_paths_py_import_os`, Module, degree: 1)

## Relationships

- services_batch_processor_utils_file_paths_py → services_batch_processor_utils_file_paths_py_import_os (imports)
- services_batch_processor_utils_file_paths_py → services_batch_processor_utils_file_paths_py_import_boto3_dynamodb_conditions_attr (imports)
- services_batch_processor_utils_file_paths_py → services_batch_processor_utils_file_paths_py_import_core_get_dynamo_table (imports)
- services_batch_processor_utils_file_paths_py → services_batch_processor_utils_file_paths_py_get_completed_paths (defines)
- services_batch_processor_utils_file_paths_py → services_batch_processor_utils_file_paths_py_get_failed_paths (defines)

