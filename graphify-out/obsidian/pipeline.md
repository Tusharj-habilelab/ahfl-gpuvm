---
id: core_pipeline_py
type: File
source: ./core/pipeline.py
community: 3
community_label: typing.Tuple
---

## Connections

- [[gc]] (imports)
- [[logging]] (imports)
- [[threading]] (imports)
- [[time]] (imports)
- [[typing_Any]] (imports)
- [[typing_Dict]] (imports)
- [[typing_Optional]] (imports)
- [[typing_Tuple]] (imports)
- [[cv2]] (imports)
- [[numpy]] (imports)
- [[core_aadhaar_gate_run_full_gate_scoring]] (imports)
- [[core_classifiers_is_aadhaar_card_confirmed]] (imports)
- [[core_classifiers_is_pan_card]] (imports)
- [[core_classifiers_mask_pvc_aadhaar]] (imports)
- [[core_config_ROUTER_CONFIDENCE_THRESHOLD]] (imports)
- [[core_config_ROUTER_ENABLED]] (imports)
- [[core_config_SKIP_KEYWORDS]] (imports)
- [[core_ocr_masking_find_aadhaar_patterns]] (imports)
- [[core_ocr_masking_mask_ocr_detections]] (imports)
- [[core_ocr_masking_mask_yolo_detections]] (imports)
- [[core_ocr_ocr_adapter_adapt_paddle_result]] (imports)
- [[core_ocr_ocr_adapter_get_texts_and_boxes]] (imports)
- [[core_ocr_paddle_create_paddle_ocr]] (imports)
- [[core_ocr_paddle_get_doc_orientation_model]] (imports)
- [[core_ocr_paddle_resize_image_for_ocr]] (imports)
- [[core_ocr_paddle_run_ocr_lite_for_routing]] (imports)
- [[core_ocr_paddle_scale_adapted_ocr_results]] (imports)
- [[core_router_classify_document_lane]] (imports)
- [[core_utils_angle_detector_find_best_orientation]] (imports)
- [[_get_ocr__]] (defines)
- [[_correct_doc_orientation__]] (defines)
- [[_run_ocr_on_region__]] (defines)
- [[_verify_skip_pan__]] (defines)
- [[_report_mask_counts__]] (defines)
- [[_empty_yolo_report__]] (defines)
- [[_derive_yolo_report_from_dets__]] (defines)
- [[_run_ocr_for_card_path__]] (defines)
- [[_process_form_lane__]] (defines)
- [[_process_card_like_lane__]] (defines)
- [[process_image__]] (defines)
