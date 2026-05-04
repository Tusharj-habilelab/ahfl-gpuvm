# Community 25: run_batch_s3()

**Members:** 6

## Nodes

- **_cleanup_stale_processing_records()** (`services_batch_processor_batch_py_cleanup_stale_processing_records`, Function, degree: 2)
- **_dynamo_retry()** (`services_batch_processor_batch_py_dynamo_retry`, Function, degree: 2)
- **_list_s3_keys()** (`services_batch_processor_batch_py_list_s3_keys`, Function, degree: 2)
- **_process_image()** (`services_batch_processor_batch_py_process_image`, Function, degree: 4)
- **_process_pdf()** (`services_batch_processor_batch_py_process_pdf`, Function, degree: 4)
- **run_batch_s3()** (`services_batch_processor_batch_py_run_batch_s3`, Function, degree: 9)

## Relationships

- services_batch_processor_batch_py_process_pdf → services_batch_processor_batch_py_process_image (calls)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_list_s3_keys (calls)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_cleanup_stale_processing_records (calls)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_process_image (calls)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_process_pdf (calls)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_dynamo_retry (calls)

