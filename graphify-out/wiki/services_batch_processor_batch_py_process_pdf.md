# _process_pdf()

- **ID:** `services_batch_processor_batch_py_process_pdf`
- **Type:** Function
- **File:** `./services/batch-processor/batch.py`
- **Location:** L508
- **Community:** 1 (_validate_s3_buckets())

## Relationships

- services_batch_processor_batch_py → services_batch_processor_batch_py_process_pdf (defines, Extracted)
- services_batch_processor_batch_py_process_pdf → services_batch_processor_batch_py_process_image (calls, Inferred)
- services_batch_processor_batch_py_run_batch → services_batch_processor_batch_py_process_pdf (calls, Inferred)
- services_batch_processor_batch_py_run_batch_s3 → services_batch_processor_batch_py_process_pdf (calls, Inferred)

