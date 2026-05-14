# 📊 Graph Analysis Report

**Root:** `.`

## Summary

| Metric | Value |
|--------|-------|
| Nodes | 116 |
| Edges | 140 |
| Communities | 10 |
| Hyperedges | 0 |

### Confidence Breakdown

| Level | Count | Percentage |
|-------|-------|------------|
| EXTRACTED | 110 | 78.6% |
| INFERRED | 30 | 21.4% |
| AMBIGUOUS | 0 | 0.0% |

## 🌟 God Nodes (Most Connected)

| Node | Degree | Community |
|------|--------|-----------|
| pipeline-visualizer-per-step | 63 | 0 |
| run_debug() | 21 | 1 |
| router | 19 | 2 |
| validate_config | 10 | 3 |
| check_dynamo_table | 7 | 4 |
| export_session_to_json | 6 | 5 |
| GPU_MASTER_SYNC | 5 | 6 |
| classify_document_lane() | 5 | 7 |
| _run_gate_once() | 4 | 9 |
| _bbox_from_poly() | 4 | 8 |

## 🔮 Surprising Connections

- **pipeline_visualizer_per_step_py_run_debug** → **pipeline_visualizer_per_step_py_draw_tokens** (calls)
- **pipeline_visualizer_per_step_py_run_debug** → **pipeline_visualizer_per_step_py_draw_detected_words** (calls)
- **pipeline_visualizer_per_step_py_run_debug** → **pipeline_visualizer_per_step_py_run_gate_once** (calls)
- **pipeline_visualizer_per_step_py_run_debug** → **pipeline_visualizer_per_step_py_bbox_from_poly** (calls)
- **pipeline_visualizer_per_step_py_main** → **pipeline_visualizer_per_step_py_run_debug** (calls)

## 🏘️ Communities

### Community 0 — _draw_poly_regions() (42 nodes, cohesion: 0.05)

- pipeline-visualizer-per-step
- _draw_poly_regions()
- argparse
- core.classifiers.detect_aadhaar_side
- core.classifiers.is_aadhaar_card_confirmed
- core.classifiers.mask_pvc_aadhaar
- core.config.GPU_ENABLED
- core.config.ROUTER_CONFIDENCE_THRESHOLD
- core.config.ROUTER_ENABLED
- core.config.YOLO_MAIN_DILATE_ENABLED
- core.models.yolo_runner.get_yolo_best
- core.models.yolo_runner.get_yolo_main
- core.ocr.masking.find_aadhaar_patterns
- core.ocr.masking.mask_ocr_detections
- core.ocr.masking.mask_yolo_detections
- core.ocr.masking.merge_detections
- core.ocr.masking.yolo_results_to_detections
- core.ocr.paddle.run_ocr_lite_for_routing
- core.pipeline._correct_doc_orientation
- core.pipeline._get_ocr
- _…and 22 more_

### Community 1 — _tokens_from_ocr() (16 nodes, cohesion: 0.13)

- _attach_file_logger()
- _box_area()
- _build_db_parity_report()
- _count_labels()
- _derive_yolo_report_from_dets()
- _detach_file_logger()
- _draw_boxes()
- _draw_token_polygons()
- _make_tree()
- _na_marker()
- _rect_intersection()
- _rot()
- run_debug()
- _save_image()
- _save_json()
- _tokens_from_ocr()

### Community 2 — typing.Tuple (15 nodes, cohesion: 0.13)

- router
- core.config.ROUTER_BIAS_RATIO
- core.config.ROUTER_CARD_CONF_DIVISOR
- core.config.ROUTER_CARD_TOKEN_MAX
- core.config.ROUTER_CONFIDENCE_THRESHOLD
- core.config.ROUTER_FORM_CONF_DIVISOR
- core.config.ROUTER_FORM_TOKEN_MIN
- core.config.ROUTER_MIXED_CONFIDENCE
- core.config.ROUTER_TABLE_SIGNAL_MIN
- core.config.SKIP_KEYWORDS
- logging
- numpy
- re
- typing.Dict
- typing.Tuple

### Community 3 — check() (11 nodes, cohesion: 0.18)

- validate_config
- check()
- boto3
- botocore.config.Config
- botocore.exceptions.ClientError
- dotenv.load_dotenv
- os
- paddleocr.PaddleOCR
- pathlib.Path
- sys
- torch

### Community 4 — check_table() (8 nodes, cohesion: 0.25)

- check_dynamo_table
- check_table()
- argparse
- boto3
- botocore.exceptions.ClientError
- dotenv.load_dotenv
- os
- sys

### Community 5 — to_ms() (7 nodes, cohesion: 0.33)

- export_session_to_json
- datetime
- json
- pathlib.Path
- sys
- main()
- to_ms()

### Community 6 — write_file() (6 nodes, cohesion: 0.33)

- GPU_MASTER_SYNC
- append_after()
- os
- sys
- patch()
- write_file()

### Community 7 — _normalize_text() (5 nodes, cohesion: 0.40)

- classify_document_lane()
- _contains_card_signals()
- _contains_form_signals()
- _contains_skip_signals()
- _normalize_text()

### Community 8 — _draw_tokens() (3 nodes, cohesion: 0.67)

- _bbox_from_poly()
- _draw_detected_words()
- _draw_tokens()

### Community 9 — _run_gate_once() (3 nodes, cohesion: 0.67)

- main()
- _preprocess_grey()
- _run_gate_once()

## 🕳️ Knowledge Gaps

No isolated nodes.

## 💰 Token Cost

| File | Tokens |
|------|--------|
| input | 0 |
| output | 0 |
| **Total** | **0** |

## ❓ Suggested Questions

1. How does 'pipeline_visualizer_per_step_py_main' relate to 3 different communities (_draw_poly_regions(), _run_gate_once(), _tokens_from_ocr())?
1. How does 'pipeline_visualizer_per_step_py' relate to 4 different communities (_draw_poly_regions(), _tokens_from_ocr(), _draw_tokens(), _run_gate_once())?
1. How does 'pipeline_visualizer_per_step_py_draw_detected_words' relate to 3 different communities (_draw_poly_regions(), _tokens_from_ocr(), _draw_tokens())?
1. How does 'pipeline_visualizer_per_step_py_run_gate_once' relate to 3 different communities (_draw_poly_regions(), _run_gate_once(), _tokens_from_ocr())?
1. How does 'pipeline_visualizer_per_step_py_draw_tokens' relate to 3 different communities (_draw_poly_regions(), _tokens_from_ocr(), _draw_tokens())?
1. How does 'pipeline_visualizer_per_step_py_run_debug' relate to 4 different communities (_run_gate_once(), _draw_tokens(), _tokens_from_ocr(), _draw_poly_regions())?
1. How does 'pipeline_visualizer_per_step_py_bbox_from_poly' relate to 3 different communities (_draw_tokens(), _draw_poly_regions(), _tokens_from_ocr())?

---
_Generated by graphify-rs_
