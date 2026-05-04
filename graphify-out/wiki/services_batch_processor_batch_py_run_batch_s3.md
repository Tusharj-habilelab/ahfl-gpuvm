# run_batch_s3()

- **ID:** `services_batch_processor_batch_py_run_batch_s3`
- **Type:** Function
- **File:** `./services/batch-processor/batch.py`
- **Location:** L792
- **Community:** 25 (run_batch_s3())

## Relationships

- services_batch_processor_batch_py → services_batch_processor_batch_py_run_batch_s3 (defines, Extracted)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_is_password_protected_pdf (calls, Inferred)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_list_s3_keys (calls, Inferred)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_cleanup_stale_processing_records (calls, Inferred)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_process_image (calls, Inferred)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_update_to_error (calls, Inferred)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_process_pdf (calls, Inferred)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_get_skip_paths (calls, Inferred)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_dynamo_retry (calls, Inferred)

