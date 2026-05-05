# Community 11: scale_adapted_ocr_results()

**Members:** 16

## Nodes

- **paddle** (`core_ocr_paddle_py`, File, degree: 15)
- **create_paddle_ocr()** (`core_ocr_paddle_py_create_paddle_ocr`, Function, degree: 2)
- **_env_int()** (`core_ocr_paddle_py_env_int`, Function, degree: 1)
- **get_doc_orientation_model()** (`core_ocr_paddle_py_get_doc_orientation_model`, Function, degree: 1)
- **core.config.PADDLE_OCR_MAX_SIDE** (`core_ocr_paddle_py_import_core_config_paddle_ocr_max_side`, Module, degree: 1)
- **core.config.ROUTER_OCR_LITE_MAX_SIDE** (`core_ocr_paddle_py_import_core_config_router_ocr_lite_max_side`, Module, degree: 1)
- **core.config.ROUTER_OCR_LITE_MAX_TOKENS** (`core_ocr_paddle_py_import_core_config_router_ocr_lite_max_tokens`, Module, degree: 1)
- **cv2** (`core_ocr_paddle_py_import_cv2`, Module, degree: 1)
- **os** (`core_ocr_paddle_py_import_os`, Module, degree: 1)
- **paddleocr.DocImgOrientationClassification** (`core_ocr_paddle_py_import_paddleocr_docimgorientationclassification`, Module, degree: 1)
- **paddleocr.PaddleOCR** (`core_ocr_paddle_py_import_paddleocr_paddleocr`, Module, degree: 1)
- **threading** (`core_ocr_paddle_py_import_threading`, Module, degree: 1)
- **typing.Optional** (`core_ocr_paddle_py_import_typing_optional`, Module, degree: 1)
- **resize_image_for_ocr()** (`core_ocr_paddle_py_resize_image_for_ocr`, Function, degree: 1)
- **run_ocr_lite_for_routing()** (`core_ocr_paddle_py_run_ocr_lite_for_routing`, Function, degree: 2)
- **scale_adapted_ocr_results()** (`core_ocr_paddle_py_scale_adapted_ocr_results`, Function, degree: 1)

## Relationships

- core_ocr_paddle_py → core_ocr_paddle_py_import_os (imports)
- core_ocr_paddle_py → core_ocr_paddle_py_import_threading (imports)
- core_ocr_paddle_py → core_ocr_paddle_py_import_cv2 (imports)
- core_ocr_paddle_py → core_ocr_paddle_py_import_typing_optional (imports)
- core_ocr_paddle_py → core_ocr_paddle_py_import_paddleocr_paddleocr (imports)
- core_ocr_paddle_py → core_ocr_paddle_py_import_paddleocr_docimgorientationclassification (imports)
- core_ocr_paddle_py → core_ocr_paddle_py_import_core_config_paddle_ocr_max_side (imports)
- core_ocr_paddle_py → core_ocr_paddle_py_import_core_config_router_ocr_lite_max_side (imports)
- core_ocr_paddle_py → core_ocr_paddle_py_import_core_config_router_ocr_lite_max_tokens (imports)
- core_ocr_paddle_py → core_ocr_paddle_py_env_int (defines)
- core_ocr_paddle_py → core_ocr_paddle_py_create_paddle_ocr (defines)
- core_ocr_paddle_py → core_ocr_paddle_py_get_doc_orientation_model (defines)
- core_ocr_paddle_py → core_ocr_paddle_py_resize_image_for_ocr (defines)
- core_ocr_paddle_py → core_ocr_paddle_py_scale_adapted_ocr_results (defines)
- core_ocr_paddle_py → core_ocr_paddle_py_run_ocr_lite_for_routing (defines)
- core_ocr_paddle_py_run_ocr_lite_for_routing → core_ocr_paddle_py_create_paddle_ocr (calls)

