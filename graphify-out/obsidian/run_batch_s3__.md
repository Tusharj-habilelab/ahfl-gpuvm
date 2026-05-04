---
id: services_batch_processor_batch_py_run_batch_s3
type: Function
source: ./services/batch-processor/batch.py
community: 25
community_label: run_batch_s3()
---

## Connections

- [[batch]] (defines)
- [[_is_password_protected_pdf__]] (calls)
- [[_list_s3_keys__]] (calls)
- [[_cleanup_stale_processing_records__]] (calls)
- [[_process_image__]] (calls)
- [[_update_to_error__]] (calls)
- [[_process_pdf__]] (calls)
- [[_get_skip_paths__]] (calls)
- [[_dynamo_retry__]] (calls)
