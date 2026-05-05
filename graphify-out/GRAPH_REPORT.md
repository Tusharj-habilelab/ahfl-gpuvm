# 📊 Graph Analysis Report

**Root:** `.`

## Summary

| Metric | Value |
|--------|-------|
| Nodes | 549 |
| Edges | 585 |
| Communities | 47 |
| Hyperedges | 0 |

### Confidence Breakdown

| Level | Count | Percentage |
|-------|-------|------------|
| EXTRACTED | 506 | 86.5% |
| INFERRED | 79 | 13.5% |
| AMBIGUOUS | 0 | 0.0% |

## 🌟 God Nodes (Most Connected)

| Node | Degree | Community |
|------|--------|-----------|
| batch | 65 | 1 |
| __init__ | 57 | 0 |
| pipeline | 40 | 2 |
| engine | 36 | 3 |
| masking | 28 | 4 |
| api-gateway::main | 20 | 5 |
| classifiers | 20 | 6 |
| aadhaar_gate | 18 | 8 |
| angle_detector | 18 | 7 |
| __init__ | 15 | 10 |

## 🔮 Surprising Connections

- **core_ocr_masking_py_find_aadhaar_patterns** → **core_ocr_masking_py_is_valid_aadhaar_number** (calls)
- **services_batch_processor_batch_py_run_batch** → **services_batch_processor_batch_py_is_password_protected_pdf** (calls)
- **services_batch_processor_batch_py_run_batch** → **services_batch_processor_batch_py_process_pdf** (calls)
- **services_batch_processor_batch_py_run_batch** → **services_batch_processor_batch_py_process_image** (calls)
- **services_batch_processor_batch_py_run_batch** → **services_batch_processor_batch_py_update_to_completed** (calls)

## 🏘️ Communities

### Community 0 — .utils.file_utils.validate_file_size (58 nodes, cohesion: 0.03)

- __init__
- .aadhaar_gate.run_full_gate_scoring
- .classifiers.detect_aadhaar_side
- .classifiers.is_aadhaar_card_confirmed
- .classifiers.is_pan_card
- .config.API_GATEWAY_PORT
- .config.COMMIT_BATCH_SIZE
- .config.GPU_MEMORY_FRACTION
- .config.GPU_WARMUP_ENABLED
- .config.HOST
- .config.LOG_LEVEL
- .config.MASKING_ENGINE_URL
- .config.MODEL_BEST
- .config.MODEL_FRONT_BACK
- .config.MODEL_MAIN
- .config.ORIENTATION_ANGLES
- .config.ORIENTATION_EARLY_EXIT_CONF
- .config.ORIENTATION_ENABLED
- .config.OUTPUT_FOLDER
- .config.PADDLE_MODEL_DIR
- _…and 38 more_

### Community 1 — _validate_s3_buckets() (56 nodes, cohesion: 0.04)

- batch
- _extract_path()
- _handle_shutdown()
- argparse
- boto3
- boto3.dynamodb.conditions.Attr
- boto3.dynamodb.conditions.Key
- botocore.config.Config
- botocore.exceptions.ClientError
- core.config.BATCH_PATH_SKIP_KEYWORDS
- core.config.COMMIT_BATCH_SIZE
- core.config.GPU_ENABLED
- core.config.GPU_MEMORY_FRACTION
- core.config.GPU_WARMUP_ENABLED
- core.config.MAX_PDF_PAGES
- core.config.MAX_S3_FILE_SIZE
- core.config.PDF_CHUNK_SIZE
- core.config.STALE_PROCESSING_HOURS
- core.config.validate_required_env_vars
- core.count_files_in_folder
- _…and 36 more_

### Community 2 — _verify_skip_pan() (41 nodes, cohesion: 0.07)

- pipeline
- _correct_doc_orientation()
- _derive_yolo_report_from_dets()
- _empty_yolo_report()
- _get_ocr()
- core.aadhaar_gate.run_full_gate_scoring
- core.classifiers.is_aadhaar_card_confirmed
- core.classifiers.is_pan_card
- core.classifiers.mask_pvc_aadhaar
- core.config.ROUTER_CONFIDENCE_THRESHOLD
- core.config.ROUTER_ENABLED
- core.config.SKIP_KEYWORDS
- core.ocr.masking.find_aadhaar_patterns
- core.ocr.masking.mask_ocr_detections
- core.ocr.masking.mask_yolo_detections
- core.ocr.ocr_adapter.adapt_paddle_result
- core.ocr.ocr_adapter.get_texts_and_boxes
- core.ocr.paddle.create_paddle_ocr
- core.ocr.paddle.get_doc_orientation_model
- core.ocr.paddle.resize_image_for_ocr
- _…and 21 more_

### Community 3 — startup_event() (37 nodes, cohesion: 0.06)

- engine
- get_output_file()
- health()
- health_detailed()
- asyncio
- core.config.GPU_ENABLED
- core.config.GPU_MEMORY_FRACTION
- core.config.MAX_FILE_SIZE
- core.config.PDF_CHUNK_SIZE
- core.config.validate_required_env_vars
- core.get_yolo_best
- core.get_yolo_main
- dotenv.load_dotenv
- fastapi.FastAPI
- fastapi.File
- fastapi.HTTPException
- fastapi.middleware.cors.CORSMiddleware
- fastapi.responses.FileResponse
- fastapi.responses.JSONResponse
- fastapi.UploadFile
- _…and 17 more_

### Community 4 — yolo_results_to_detections() (22 nodes, cohesion: 0.13)

- masking
- calculate_iou()
- check_image_text()
- compute_digit_mask_region()
- collections.Counter
- core.ocr.ocr_adapter.adapt_paddle_result
- core.ocr.ocr_adapter.get_texts_and_boxes
- core.ocr.paddle.create_paddle_ocr
- cv2
- logging
- math
- numpy
- re
- time
- is_valid_aadhaar_number()
- mask_ocr_detections()
- mask_yolo_detections()
- merge_detections()
- _ocr_verify_and_mask_number()
- uid_table_masking_coordinates()
- _…and 2 more_

### Community 5 — _validate_api_key() (21 nodes, cohesion: 0.10)

- main
- create_upload_file()
- health()
- dotenv.load_dotenv
- fastapi.FastAPI
- fastapi.File
- fastapi.Header
- fastapi.HTTPException
- fastapi.middleware.cors.CORSMiddleware
- fastapi.responses.FileResponse
- fastapi.responses.JSONResponse
- fastapi.UploadFile
- hmac
- httpx
- mimetypes
- os
- pathlib.Path
- uvicorn
- _load_api_keys()
- serve_masked_file()
- _…and 1 more_

### Community 6 — normalize_aadhaar_keyword() (21 nodes, cohesion: 0.11)

- classifiers
- detect_aadhaar_side()
- _get_classifier()
- _get_person_model()
- core.config.PVC_MAX_ROTATIONS
- core.config.PVC_PERSON_CONFIDENCE_THRESHOLD
- cv2
- dotenv.load_dotenv
- logging
- numpy
- os
- re
- threading
- torch
- typing.List
- typing.Tuple
- ultralytics.YOLO
- is_aadhaar_card_confirmed()
- is_pan_card()
- mask_pvc_aadhaar()
- _…and 1 more_

### Community 7 — rotate_image_affine() (19 nodes, cohesion: 0.13)

- angle_detector
- _check_composite_early_exit()
- find_best_orientation()
- _get_doc_orientation_hint()
- core.config.ORIENTATION_ANGLES
- core.config.ORIENTATION_ENABLED
- core.config.ORIENTATION_STRONG_THRESHOLD
- core.config.ORIENTATION_TARGET_THRESHOLD
- core.ocr.paddle.get_doc_orientation_model
- cv2
- logging
- numpy
- typing.Any
- typing.Callable
- typing.Dict
- typing.Tuple
- _rotate_by_angle()
- rotate_image()
- rotate_image_affine()

### Community 8 — run_full_gate_scoring() (19 nodes, cohesion: 0.12)

- aadhaar_gate
- core.classifiers.detect_aadhaar_side
- core.models.yolo_runner.get_yolo_best
- core.models.yolo_runner.get_yolo_main
- core.ocr.masking.merge_detections
- core.ocr.masking.yolo_results_to_detections
- core.spatial.filter_dets_inside_box
- core.spatial.find_aadhaar_card_boxes
- core.spatial.map_crop_dets_to_full
- cv2
- logging
- numpy
- typing.Any
- typing.Dict
- typing.List
- typing.Tuple
- _preprocess_greyscale()
- _process_single_aadhaar_crop()
- run_full_gate_scoring()

### Community 9 — scale_adapted_ocr_results() (16 nodes, cohesion: 0.13)

- paddle
- create_paddle_ocr()
- _env_int()
- get_doc_orientation_model()
- core.config.PADDLE_OCR_MAX_SIDE
- core.config.ROUTER_OCR_LITE_MAX_SIDE
- core.config.ROUTER_OCR_LITE_MAX_TOKENS
- cv2
- os
- paddleocr.DocImgOrientationClassification
- paddleocr.PaddleOCR
- threading
- typing.Optional
- resize_image_for_ocr()
- run_ocr_lite_for_routing()
- scale_adapted_ocr_results()

### Community 10 — .paddle.scale_adapted_ocr_results (16 nodes, cohesion: 0.13)

- __init__
- .masking.compute_digit_mask_region
- .masking.cosine_similarity
- .masking.find_aadhaar_patterns
- .masking.is_valid_aadhaar_number
- .masking.levenshtein_score
- .masking.mask_ocr_detections
- .masking.mask_yolo_detections
- .masking.merge_detections
- .masking.verhoeff_validate
- .masking.yolo_results_to_detections
- .ocr_adapter.adapt_paddle_result
- .ocr_adapter.get_texts_and_boxes
- .paddle.create_paddle_ocr
- .paddle.resize_image_for_ocr
- .paddle.scale_adapted_ocr_results

### Community 11 — write_mask_log() (16 nodes, cohesion: 0.14)

- log_writer
- bulk_write_logs()
- ensure_log_table()
- get_processed_paths()
- boto3.dynamodb.conditions.Attr
- .database.get_dynamo_table
- datetime.timezone
- decimal.Decimal
- logging
- math
- typing.Dict
- typing.List
- typing.Set
- uuid
- _to_decimal()
- write_mask_log()

### Community 12 — validate_file_size() (15 nodes, cohesion: 0.13)

- file_utils
- ensure_output_dir()
- get_file_extension()
- images_to_pdf()
- core.config.MAX_FILE_SIZE
- logging
- os
- pathlib.Path
- tempfile
- typing.List
- typing.Tuple
- is_supported_file()
- pdf_to_images()
- should_skip_file()
- validate_file_size()

### Community 13 — reset_models() (14 nodes, cohesion: 0.14)

- yolo_runner
- get_yolo_best()
- get_yolo_main()
- core.config.GPU_ENABLED
- dotenv.load_dotenv
- functools.lru_cache
- logging
- os
- threading
- torch
- typing.Optional
- typing.Tuple
- ultralytics.YOLO
- reset_models()

### Community 14 — .file_utils.validate_file_size (12 nodes, cohesion: 0.17)

- __init__
- .angle_detector.find_best_orientation
- .angle_detector.rotate_image
- .angle_detector.rotate_image_affine
- .counts.count_files_in_folder
- .file_utils.ensure_output_dir
- .file_utils.get_file_extension
- .file_utils.images_to_pdf
- .file_utils.is_supported_file
- .file_utils.pdf_to_images
- .file_utils.should_skip_file
- .file_utils.validate_file_size

### Community 15 — run_inference() (11 nodes, cohesion: 0.25)

- setup_and_first_inference
- check_yolo_models()
- argparse
- gc
- logging
- os
- pathlib.Path
- sys
- init_paddle_ocr()
- main()
- run_inference()

### Community 16 — export_to_csv() (10 nodes, cohesion: 0.20)

- export_logs
- export_to_csv()
- argparse
- boto3.dynamodb.conditions.Attr
- core.get_dynamo_table
- core.TABLE_NAME
- csv
- dotenv.load_dotenv
- pathlib.Path
- sys

### Community 17 — analyze_records() (9 nodes, cohesion: 0.22)

- logs
- analyze_records()
- argparse
- boto3.dynamodb.conditions.Attr
- core.get_dynamo_table
- csv
- dotenv.load_dotenv
- pathlib.Path
- sys

### Community 18 — map_dets_to_crop() (9 nodes, cohesion: 0.28)

- spatial
- compute_intersection_area()
- filter_dets_inside_box()
- find_aadhaar_card_boxes()
- find_qr_boxes()
- typing.List
- is_inside_aadhaar_by_area()
- map_crop_dets_to_full()
- map_dets_to_crop()

### Community 19 — create_table() (8 nodes, cohesion: 0.25)

- create_dynamo_table
- create_table()
- argparse
- boto3
- botocore.exceptions.ClientError
- dotenv.load_dotenv
- os
- sys

### Community 20 — split_folder_by_applications() (7 nodes, cohesion: 0.29)

- creates_batches
- argparse
- collections.defaultdict
- math
- os
- shutil
- split_folder_by_applications()

### Community 21 — format_report() (7 nodes, cohesion: 0.29)

- inspect_yolo_models
- collect_metadata()
- format_report()
- datetime
- numpy
- os
- ultralytics.YOLO

### Community 22 — get_all_files_recursive() (7 nodes, cohesion: 0.33)

- count_total_applications
- clean_string()
- extract_application_info()
- get_all_files_recursive()
- os
- pandas
- sys

### Community 23 — levenshtein_score() (7 nodes, cohesion: 0.29)

- cosine_similarity()
- extract_number_coordinates()
- extract_target_coordinates()
- find_aadhaar_patterns()
- is_four_digit_number()
- is_twelve_digit_number()
- levenshtein_score()

### Community 24 — _normalize_bbox() (6 nodes, cohesion: 0.53)

- ocr_adapter
- adapt_paddle_result()
- _append_v3_result()
- get_texts_and_boxes()
- logging
- _normalize_bbox()

### Community 25 — validate_required_env_vars() (6 nodes, cohesion: 0.33)

- config
- dotenv.load_dotenv
- logging
- os
- setup_logging()
- validate_required_env_vars()

### Community 26 — get_dynamo_table() (6 nodes, cohesion: 0.33)

- database
- build_default_record()
- get_dynamo_table()
- boto3
- dotenv.load_dotenv
- os

### Community 27 — get_failed_paths() (6 nodes, cohesion: 0.33)

- file_paths
- get_completed_paths()
- get_failed_paths()
- boto3.dynamodb.conditions.Attr
- core.get_dynamo_table
- os

### Community 28 — write_file() (6 nodes, cohesion: 0.33)

- GPU_MASTER_SYNC_D4_COMPLETE
- append_after()
- os
- sys
- patch()
- write_file()

### Community 29 — run_batch_s3() (5 nodes, cohesion: 0.40)

- _cleanup_stale_processing_records()
- _dynamo_retry()
- _is_password_protected_pdf()
- _list_s3_keys()
- run_batch_s3()

### Community 30 — get_all_files_recursive() (30) (5 nodes, cohesion: 0.40)

- count_total_application
- count_unique_applications()
- get_all_files_recursive()
- os
- sys

### Community 31 — _write_pending() (5 nodes, cohesion: 0.40)

- _get_skip_paths()
- run_batch()
- _update_to_error()
- _update_to_processing()
- _write_pending()

### Community 32 — YOLORunner (5 nodes, cohesion: 0.60)

- YOLORunner
- .get_best()
- .get_main()
- .__init__()
- .run_inference()

### Community 33 — log_file_paths_to_csv() (5 nodes, cohesion: 0.40)

- log_file_paths
- argparse
- csv
- os
- log_file_paths_to_csv()

### Community 34 — .yolo_runner.YOLORunner (4 nodes, cohesion: 0.50)

- __init__
- .yolo_runner.get_yolo_best
- .yolo_runner.get_yolo_main
- .yolo_runner.YOLORunner

### Community 35 — shutil (35) (4 nodes, cohesion: 0.50)

- copy_files
- os
- pandas
- shutil

### Community 36 — count_pdf_pages() (4 nodes, cohesion: 0.50)

- counts
- count_files_in_folder()
- count_pdf_pages()
- os

### Community 37 — shutil (4 nodes, cohesion: 0.50)

- copy_files
- os
- pandas
- shutil

### Community 38 — pandas (3 nodes, cohesion: 0.67)

- merge_csvs
- os
- pandas

### Community 39 — .log_writer.write_mask_log (3 nodes, cohesion: 0.67)

- __init__
- .database.get_dynamo_table
- .log_writer.write_mask_log

### Community 40 — pandas (40) (3 nodes, cohesion: 0.67)

- merge_metadata
- os
- pandas

### Community 41 — pandas (41) (3 nodes, cohesion: 0.67)

- count_processed_files
- os
- pandas

### Community 42 — pandas (42) (3 nodes, cohesion: 0.67)

- main
- os
- pandas

### Community 43 — pandas (43) (2 nodes, cohesion: 1.00)

- mapping
- pandas

### Community 44 — D4_PATCHES_FOR_GPU (1 nodes, cohesion: 1.00)

- D4_PATCHES_FOR_GPU

### Community 45 — merge_chat_sessions (1 nodes, cohesion: 1.00)

- merge_chat_sessions

### Community 46 — dms_push (1 nodes, cohesion: 1.00)

- dms_push

## 🕳️ Knowledge Gaps

**Isolated nodes** (3):
- D4_PATCHES_FOR_GPU
- merge_chat_sessions
- dms_push

**Thin communities** (< 3 nodes): 4 communities

## 💰 Token Cost

| File | Tokens |
|------|--------|
| output | 0 |
| input | 0 |
| **Total** | **0** |

## ❓ Suggested Questions

1. How does 'services_batch_processor_batch_py_run_batch' relate to 3 different communities (run_batch_s3(), _validate_s3_buckets(), _write_pending())?
1. How does 'services_batch_processor_batch_py_get_skip_paths' relate to 3 different communities (_write_pending(), run_batch_s3(), _validate_s3_buckets())?
1. How does 'services_batch_processor_batch_py_run_batch_s3' relate to 3 different communities (_validate_s3_buckets(), run_batch_s3(), _write_pending())?
1. How does 'services_batch_processor_batch_py' relate to 3 different communities (run_batch_s3(), _validate_s3_buckets(), _write_pending())?
1. How does 'services_batch_processor_batch_py_process_image' relate to 3 different communities (_write_pending(), run_batch_s3(), _validate_s3_buckets())?
1. How does 'services_batch_processor_batch_py_is_password_protected_pdf' relate to 3 different communities (run_batch_s3(), _write_pending(), _validate_s3_buckets())?
1. How does 'services_batch_processor_batch_py_process_pdf' relate to 3 different communities (_write_pending(), _validate_s3_buckets(), run_batch_s3())?

---
_Generated by graphify-rs_
