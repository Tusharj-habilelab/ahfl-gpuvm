# Community 9: .paddle.scale_adapted_ocr_results

**Members:** 16

## Nodes

- **__init__** (`core_ocr_init_py`, File, degree: 15)
- **.masking.compute_digit_mask_region** (`core_ocr_init_py_import_masking_compute_digit_mask_region`, Module, degree: 1)
- **.masking.cosine_similarity** (`core_ocr_init_py_import_masking_cosine_similarity`, Module, degree: 1)
- **.masking.find_aadhaar_patterns** (`core_ocr_init_py_import_masking_find_aadhaar_patterns`, Module, degree: 1)
- **.masking.is_valid_aadhaar_number** (`core_ocr_init_py_import_masking_is_valid_aadhaar_number`, Module, degree: 1)
- **.masking.levenshtein_score** (`core_ocr_init_py_import_masking_levenshtein_score`, Module, degree: 1)
- **.masking.mask_ocr_detections** (`core_ocr_init_py_import_masking_mask_ocr_detections`, Module, degree: 1)
- **.masking.mask_yolo_detections** (`core_ocr_init_py_import_masking_mask_yolo_detections`, Module, degree: 1)
- **.masking.merge_detections** (`core_ocr_init_py_import_masking_merge_detections`, Module, degree: 1)
- **.masking.verhoeff_validate** (`core_ocr_init_py_import_masking_verhoeff_validate`, Module, degree: 1)
- **.masking.yolo_results_to_detections** (`core_ocr_init_py_import_masking_yolo_results_to_detections`, Module, degree: 1)
- **.ocr_adapter.adapt_paddle_result** (`core_ocr_init_py_import_ocr_adapter_adapt_paddle_result`, Module, degree: 1)
- **.ocr_adapter.get_texts_and_boxes** (`core_ocr_init_py_import_ocr_adapter_get_texts_and_boxes`, Module, degree: 1)
- **.paddle.create_paddle_ocr** (`core_ocr_init_py_import_paddle_create_paddle_ocr`, Module, degree: 1)
- **.paddle.resize_image_for_ocr** (`core_ocr_init_py_import_paddle_resize_image_for_ocr`, Module, degree: 1)
- **.paddle.scale_adapted_ocr_results** (`core_ocr_init_py_import_paddle_scale_adapted_ocr_results`, Module, degree: 1)

## Relationships

- core_ocr_init_py → core_ocr_init_py_import_masking_find_aadhaar_patterns (imports)
- core_ocr_init_py → core_ocr_init_py_import_masking_mask_ocr_detections (imports)
- core_ocr_init_py → core_ocr_init_py_import_masking_mask_yolo_detections (imports)
- core_ocr_init_py → core_ocr_init_py_import_masking_merge_detections (imports)
- core_ocr_init_py → core_ocr_init_py_import_masking_yolo_results_to_detections (imports)
- core_ocr_init_py → core_ocr_init_py_import_masking_verhoeff_validate (imports)
- core_ocr_init_py → core_ocr_init_py_import_masking_is_valid_aadhaar_number (imports)
- core_ocr_init_py → core_ocr_init_py_import_masking_compute_digit_mask_region (imports)
- core_ocr_init_py → core_ocr_init_py_import_masking_cosine_similarity (imports)
- core_ocr_init_py → core_ocr_init_py_import_masking_levenshtein_score (imports)
- core_ocr_init_py → core_ocr_init_py_import_ocr_adapter_adapt_paddle_result (imports)
- core_ocr_init_py → core_ocr_init_py_import_ocr_adapter_get_texts_and_boxes (imports)
- core_ocr_init_py → core_ocr_init_py_import_paddle_create_paddle_ocr (imports)
- core_ocr_init_py → core_ocr_init_py_import_paddle_resize_image_for_ocr (imports)
- core_ocr_init_py → core_ocr_init_py_import_paddle_scale_adapted_ocr_results (imports)

