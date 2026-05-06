# Community 31: _write_pending()

**Members:** 5

## Nodes

- **_get_skip_paths()** (`services_batch_processor_batch_py_get_skip_paths`, Function, degree: 3)
- **run_batch()** (`services_batch_processor_batch_py_run_batch`, Function, degree: 9)
- **_update_to_error()** (`services_batch_processor_batch_py_update_to_error`, Function, degree: 3)
- **_update_to_processing()** (`services_batch_processor_batch_py_update_to_processing`, Function, degree: 2)
- **_write_pending()** (`services_batch_processor_batch_py_write_pending`, Function, degree: 2)

## Relationships

- services_batch_processor_batch_py_run_batch → services_batch_processor_batch_py_update_to_error (calls)
- services_batch_processor_batch_py_run_batch → services_batch_processor_batch_py_write_pending (calls)
- services_batch_processor_batch_py_run_batch → services_batch_processor_batch_py_update_to_processing (calls)
- services_batch_processor_batch_py_run_batch → services_batch_processor_batch_py_get_skip_paths (calls)

