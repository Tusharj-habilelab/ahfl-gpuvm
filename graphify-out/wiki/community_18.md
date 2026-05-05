# Community 18: analyze_records()

**Members:** 9

## Nodes

- **logs** (`scripts_operational_logs_py`, File, degree: 8)
- **analyze_records()** (`scripts_operational_logs_py_analyze_records`, Function, degree: 1)
- **argparse** (`scripts_operational_logs_py_import_argparse`, Module, degree: 1)
- **boto3.dynamodb.conditions.Attr** (`scripts_operational_logs_py_import_boto3_dynamodb_conditions_attr`, Module, degree: 1)
- **core.get_dynamo_table** (`scripts_operational_logs_py_import_core_get_dynamo_table`, Module, degree: 1)
- **csv** (`scripts_operational_logs_py_import_csv`, Module, degree: 1)
- **dotenv.load_dotenv** (`scripts_operational_logs_py_import_dotenv_load_dotenv`, Module, degree: 1)
- **pathlib.Path** (`scripts_operational_logs_py_import_pathlib_path`, Module, degree: 1)
- **sys** (`scripts_operational_logs_py_import_sys`, Module, degree: 1)

## Relationships

- scripts_operational_logs_py → scripts_operational_logs_py_import_sys (imports)
- scripts_operational_logs_py → scripts_operational_logs_py_import_pathlib_path (imports)
- scripts_operational_logs_py → scripts_operational_logs_py_import_argparse (imports)
- scripts_operational_logs_py → scripts_operational_logs_py_import_csv (imports)
- scripts_operational_logs_py → scripts_operational_logs_py_import_dotenv_load_dotenv (imports)
- scripts_operational_logs_py → scripts_operational_logs_py_import_boto3_dynamodb_conditions_attr (imports)
- scripts_operational_logs_py → scripts_operational_logs_py_import_core_get_dynamo_table (imports)
- scripts_operational_logs_py → scripts_operational_logs_py_analyze_records (defines)

