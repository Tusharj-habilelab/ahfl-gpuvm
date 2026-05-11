# Community 26: get_dynamo_table()

**Members:** 6

## Nodes

- **database** (`core_db_database_py`, File, degree: 5)
- **build_default_record()** (`core_db_database_py_build_default_record`, Function, degree: 1)
- **get_dynamo_table()** (`core_db_database_py_get_dynamo_table`, Function, degree: 1)
- **boto3** (`core_db_database_py_import_boto3`, Module, degree: 1)
- **dotenv.load_dotenv** (`core_db_database_py_import_dotenv_load_dotenv`, Module, degree: 1)
- **os** (`core_db_database_py_import_os`, Module, degree: 1)

## Relationships

- core_db_database_py → core_db_database_py_import_os (imports)
- core_db_database_py → core_db_database_py_import_boto3 (imports)
- core_db_database_py → core_db_database_py_import_dotenv_load_dotenv (imports)
- core_db_database_py → core_db_database_py_build_default_record (defines)
- core_db_database_py → core_db_database_py_get_dynamo_table (defines)

