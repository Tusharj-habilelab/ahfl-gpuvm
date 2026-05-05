# Community 31: _update_to_error()

**Members:** 5

## Nodes

- **_cleanup_stale_processing_records()** (`services_batch_processor_batch_py_cleanup_stale_processing_records`, Function, degree: 2)
- **_dynamo_retry()** (`services_batch_processor_batch_py_dynamo_retry`, Function, degree: 2)
- **_list_s3_keys()** (`services_batch_processor_batch_py_list_s3_keys`, Function, degree: 2)
- **run_batch_s3()** (`services_batch_processor_batch_py_run_batch_s3`, Function, degree: 9)
- **_update_to_error()** (`services_batch_processor_batch_py_update_to_error`, Function, degree: 3)

## Relationships

- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_update_to_error (calls)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_cleanup_stale_processing_records (calls)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_list_s3_keys (calls)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_dynamo_retry (calls)

