# Community 26: validate_required_env_vars()

**Members:** 6

## Nodes

- **config** (`core_config_py`, File, degree: 5)
- **dotenv.load_dotenv** (`core_config_py_import_dotenv_load_dotenv`, Module, degree: 1)
- **logging** (`core_config_py_import_logging`, Module, degree: 1)
- **os** (`core_config_py_import_os`, Module, degree: 1)
- **setup_logging()** (`core_config_py_setup_logging`, Function, degree: 1)
- **validate_required_env_vars()** (`core_config_py_validate_required_env_vars`, Function, degree: 1)

## Relationships

- core_config_py → core_config_py_import_os (imports)
- core_config_py → core_config_py_import_logging (imports)
- core_config_py → core_config_py_import_dotenv_load_dotenv (imports)
- core_config_py → core_config_py_validate_required_env_vars (defines)
- core_config_py → core_config_py_setup_logging (defines)

