# Community 6: run_full_gate_scoring()

**Members:** 19

## Nodes

- **aadhaar_gate** (`core_aadhaar_gate_py`, File, degree: 18)
- **core.classifiers.detect_aadhaar_side** (`core_aadhaar_gate_py_import_core_classifiers_detect_aadhaar_side`, Module, degree: 1)
- **core.models.yolo_runner.get_yolo_best** (`core_aadhaar_gate_py_import_core_models_yolo_runner_get_yolo_best`, Module, degree: 1)
- **core.models.yolo_runner.get_yolo_main** (`core_aadhaar_gate_py_import_core_models_yolo_runner_get_yolo_main`, Module, degree: 1)
- **core.ocr.masking.merge_detections** (`core_aadhaar_gate_py_import_core_ocr_masking_merge_detections`, Module, degree: 1)
- **core.ocr.masking.yolo_results_to_detections** (`core_aadhaar_gate_py_import_core_ocr_masking_yolo_results_to_detections`, Module, degree: 1)
- **core.spatial.filter_dets_inside_box** (`core_aadhaar_gate_py_import_core_spatial_filter_dets_inside_box`, Module, degree: 1)
- **core.spatial.find_aadhaar_card_boxes** (`core_aadhaar_gate_py_import_core_spatial_find_aadhaar_card_boxes`, Module, degree: 1)
- **core.spatial.map_crop_dets_to_full** (`core_aadhaar_gate_py_import_core_spatial_map_crop_dets_to_full`, Module, degree: 1)
- **cv2** (`core_aadhaar_gate_py_import_cv2`, Module, degree: 1)
- **logging** (`core_aadhaar_gate_py_import_logging`, Module, degree: 1)
- **numpy** (`core_aadhaar_gate_py_import_numpy`, Module, degree: 1)
- **typing.Any** (`core_aadhaar_gate_py_import_typing_any`, Module, degree: 1)
- **typing.Dict** (`core_aadhaar_gate_py_import_typing_dict`, Module, degree: 1)
- **typing.List** (`core_aadhaar_gate_py_import_typing_list`, Module, degree: 1)
- **typing.Tuple** (`core_aadhaar_gate_py_import_typing_tuple`, Module, degree: 1)
- **_preprocess_greyscale()** (`core_aadhaar_gate_py_preprocess_greyscale`, Function, degree: 2)
- **_process_single_aadhaar_crop()** (`core_aadhaar_gate_py_process_single_aadhaar_crop`, Function, degree: 2)
- **run_full_gate_scoring()** (`core_aadhaar_gate_py_run_full_gate_scoring`, Function, degree: 3)

## Relationships

- core_aadhaar_gate_py → core_aadhaar_gate_py_import_cv2 (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_logging (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_typing_any (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_typing_dict (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_typing_list (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_typing_tuple (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_numpy (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_core_models_yolo_runner_get_yolo_main (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_core_models_yolo_runner_get_yolo_best (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_core_classifiers_detect_aadhaar_side (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_core_ocr_masking_yolo_results_to_detections (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_core_ocr_masking_merge_detections (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_core_spatial_find_aadhaar_card_boxes (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_core_spatial_filter_dets_inside_box (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_import_core_spatial_map_crop_dets_to_full (imports)
- core_aadhaar_gate_py → core_aadhaar_gate_py_preprocess_greyscale (defines)
- core_aadhaar_gate_py → core_aadhaar_gate_py_process_single_aadhaar_crop (defines)
- core_aadhaar_gate_py → core_aadhaar_gate_py_run_full_gate_scoring (defines)
- core_aadhaar_gate_py_run_full_gate_scoring → core_aadhaar_gate_py_process_single_aadhaar_crop (calls)
- core_aadhaar_gate_py_run_full_gate_scoring → core_aadhaar_gate_py_preprocess_greyscale (calls)

