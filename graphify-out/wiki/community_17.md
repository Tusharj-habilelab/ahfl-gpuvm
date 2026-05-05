# Community 17: export_to_csv()

**Members:** 10

## Nodes

- **export_logs** (`scripts_reporting_export_logs_py`, File, degree: 9)
- **export_to_csv()** (`scripts_reporting_export_logs_py_export_to_csv`, Function, degree: 1)
- **argparse** (`scripts_reporting_export_logs_py_import_argparse`, Module, degree: 1)
- **boto3.dynamodb.conditions.Attr** (`scripts_reporting_export_logs_py_import_boto3_dynamodb_conditions_attr`, Module, degree: 1)
- **core.get_dynamo_table** (`scripts_reporting_export_logs_py_import_core_get_dynamo_table`, Module, degree: 1)
- **core.TABLE_NAME** (`scripts_reporting_export_logs_py_import_core_table_name`, Module, degree: 1)
- **csv** (`scripts_reporting_export_logs_py_import_csv`, Module, degree: 1)
- **dotenv.load_dotenv** (`scripts_reporting_export_logs_py_import_dotenv_load_dotenv`, Module, degree: 1)
- **pathlib.Path** (`scripts_reporting_export_logs_py_import_pathlib_path`, Module, degree: 1)
- **sys** (`scripts_reporting_export_logs_py_import_sys`, Module, degree: 1)

## Relationships

- scripts_reporting_export_logs_py → scripts_reporting_export_logs_py_import_sys (imports)
- scripts_reporting_export_logs_py → scripts_reporting_export_logs_py_import_pathlib_path (imports)
- scripts_reporting_export_logs_py → scripts_reporting_export_logs_py_import_csv (imports)
- scripts_reporting_export_logs_py → scripts_reporting_export_logs_py_import_argparse (imports)
- scripts_reporting_export_logs_py → scripts_reporting_export_logs_py_import_dotenv_load_dotenv (imports)
- scripts_reporting_export_logs_py → scripts_reporting_export_logs_py_import_boto3_dynamodb_conditions_attr (imports)
- scripts_reporting_export_logs_py → scripts_reporting_export_logs_py_import_core_get_dynamo_table (imports)
- scripts_reporting_export_logs_py → scripts_reporting_export_logs_py_import_core_table_name (imports)
- scripts_reporting_export_logs_py → scripts_reporting_export_logs_py_export_to_csv (defines)

