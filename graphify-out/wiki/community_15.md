# Community 15: _verify_skip_pan()

**Members:** 11

## Nodes

- **_correct_doc_orientation()** (`core_pipeline_py_correct_doc_orientation`, Function, degree: 3)
- **_derive_yolo_report_from_dets()** (`core_pipeline_py_derive_yolo_report_from_dets`, Function, degree: 3)
- **_empty_yolo_report()** (`core_pipeline_py_empty_yolo_report`, Function, degree: 3)
- **_get_ocr()** (`core_pipeline_py_get_ocr`, Function, degree: 2)
- **_process_card_like_lane()** (`core_pipeline_py_process_card_like_lane`, Function, degree: 6)
- **_process_form_lane()** (`core_pipeline_py_process_form_lane`, Function, degree: 7)
- **process_image()** (`core_pipeline_py_process_image`, Function, degree: 5)
- **_report_mask_counts()** (`core_pipeline_py_report_mask_counts`, Function, degree: 4)
- **_run_ocr_for_card_path()** (`core_pipeline_py_run_ocr_for_card_path`, Function, degree: 4)
- **_run_ocr_on_region()** (`core_pipeline_py_run_ocr_on_region`, Function, degree: 3)
- **_verify_skip_pan()** (`core_pipeline_py_verify_skip_pan`, Function, degree: 3)

## Relationships

- core_pipeline_py_derive_yolo_report_from_dets → core_pipeline_py_empty_yolo_report (calls)
- core_pipeline_py_run_ocr_for_card_path → core_pipeline_py_run_ocr_on_region (calls)
- core_pipeline_py_run_ocr_for_card_path → core_pipeline_py_correct_doc_orientation (calls)
- core_pipeline_py_process_form_lane → core_pipeline_py_run_ocr_on_region (calls)
- core_pipeline_py_process_form_lane → core_pipeline_py_report_mask_counts (calls)
- core_pipeline_py_process_form_lane → core_pipeline_py_correct_doc_orientation (calls)
- core_pipeline_py_process_form_lane → core_pipeline_py_verify_skip_pan (calls)
- core_pipeline_py_process_form_lane → core_pipeline_py_empty_yolo_report (calls)
- core_pipeline_py_process_card_like_lane → core_pipeline_py_report_mask_counts (calls)
- core_pipeline_py_process_card_like_lane → core_pipeline_py_derive_yolo_report_from_dets (calls)
- core_pipeline_py_process_card_like_lane → core_pipeline_py_verify_skip_pan (calls)
- core_pipeline_py_process_card_like_lane → core_pipeline_py_run_ocr_for_card_path (calls)
- core_pipeline_py_process_image → core_pipeline_py_get_ocr (calls)
- core_pipeline_py_process_image → core_pipeline_py_process_card_like_lane (calls)
- core_pipeline_py_process_image → core_pipeline_py_process_form_lane (calls)
- core_pipeline_py_process_image → core_pipeline_py_report_mask_counts (calls)

