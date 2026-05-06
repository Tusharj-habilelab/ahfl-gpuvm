# Community 11: write_mask_log()

**Members:** 16

## Nodes

- **log_writer** (`core_db_log_writer_py`, File, degree: 15)
- **bulk_write_logs()** (`core_db_log_writer_py_bulk_write_logs`, Function, degree: 2)
- **ensure_log_table()** (`core_db_log_writer_py_ensure_log_table`, Function, degree: 1)
- **get_processed_paths()** (`core_db_log_writer_py_get_processed_paths`, Function, degree: 1)
- **boto3.dynamodb.conditions.Attr** (`core_db_log_writer_py_import_boto3_dynamodb_conditions_attr`, Module, degree: 1)
- **.database.get_dynamo_table** (`core_db_log_writer_py_import_database_get_dynamo_table`, Module, degree: 1)
- **datetime.timezone** (`core_db_log_writer_py_import_datetime_timezone`, Module, degree: 1)
- **decimal.Decimal** (`core_db_log_writer_py_import_decimal_decimal`, Module, degree: 1)
- **logging** (`core_db_log_writer_py_import_logging`, Module, degree: 1)
- **math** (`core_db_log_writer_py_import_math`, Module, degree: 1)
- **typing.Dict** (`core_db_log_writer_py_import_typing_dict`, Module, degree: 1)
- **typing.List** (`core_db_log_writer_py_import_typing_list`, Module, degree: 1)
- **typing.Set** (`core_db_log_writer_py_import_typing_set`, Module, degree: 1)
- **uuid** (`core_db_log_writer_py_import_uuid`, Module, degree: 1)
- **_to_decimal()** (`core_db_log_writer_py_to_decimal`, Function, degree: 2)
- **write_mask_log()** (`core_db_log_writer_py_write_mask_log`, Function, degree: 3)

## Relationships

- core_db_log_writer_py → core_db_log_writer_py_import_logging (imports)
- core_db_log_writer_py → core_db_log_writer_py_import_uuid (imports)
- core_db_log_writer_py → core_db_log_writer_py_import_math (imports)
- core_db_log_writer_py → core_db_log_writer_py_import_decimal_decimal (imports)
- core_db_log_writer_py → core_db_log_writer_py_import_datetime_timezone (imports)
- core_db_log_writer_py → core_db_log_writer_py_import_typing_list (imports)
- core_db_log_writer_py → core_db_log_writer_py_import_typing_dict (imports)
- core_db_log_writer_py → core_db_log_writer_py_import_typing_set (imports)
- core_db_log_writer_py → core_db_log_writer_py_import_boto3_dynamodb_conditions_attr (imports)
- core_db_log_writer_py → core_db_log_writer_py_import_database_get_dynamo_table (imports)
- core_db_log_writer_py → core_db_log_writer_py_to_decimal (defines)
- core_db_log_writer_py → core_db_log_writer_py_write_mask_log (defines)
- core_db_log_writer_py → core_db_log_writer_py_bulk_write_logs (defines)
- core_db_log_writer_py → core_db_log_writer_py_get_processed_paths (defines)
- core_db_log_writer_py → core_db_log_writer_py_ensure_log_table (defines)
- core_db_log_writer_py_write_mask_log → core_db_log_writer_py_to_decimal (calls)
- core_db_log_writer_py_bulk_write_logs → core_db_log_writer_py_write_mask_log (calls)

