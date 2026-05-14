# Community 1: _tokens_from_ocr()

**Members:** 16

## Nodes

- **_attach_file_logger()** (`pipeline_visualizer_per_step_py_attach_file_logger`, Function, degree: 2)
- **_box_area()** (`pipeline_visualizer_per_step_py_box_area`, Function, degree: 2)
- **_build_db_parity_report()** (`pipeline_visualizer_per_step_py_build_db_parity_report`, Function, degree: 2)
- **_count_labels()** (`pipeline_visualizer_per_step_py_count_labels`, Function, degree: 2)
- **_derive_yolo_report_from_dets()** (`pipeline_visualizer_per_step_py_derive_yolo_report_from_dets`, Function, degree: 2)
- **_detach_file_logger()** (`pipeline_visualizer_per_step_py_detach_file_logger`, Function, degree: 2)
- **_draw_boxes()** (`pipeline_visualizer_per_step_py_draw_boxes`, Function, degree: 2)
- **_draw_token_polygons()** (`pipeline_visualizer_per_step_py_draw_token_polygons`, Function, degree: 2)
- **_make_tree()** (`pipeline_visualizer_per_step_py_make_tree`, Function, degree: 2)
- **_na_marker()** (`pipeline_visualizer_per_step_py_na_marker`, Function, degree: 3)
- **_rect_intersection()** (`pipeline_visualizer_per_step_py_rect_intersection`, Function, degree: 2)
- **_rot()** (`pipeline_visualizer_per_step_py_rot`, Function, degree: 2)
- **run_debug()** (`pipeline_visualizer_per_step_py_run_debug`, Function, degree: 21)
- **_save_image()** (`pipeline_visualizer_per_step_py_save_image`, Function, degree: 2)
- **_save_json()** (`pipeline_visualizer_per_step_py_save_json`, Function, degree: 3)
- **_tokens_from_ocr()** (`pipeline_visualizer_per_step_py_tokens_from_ocr`, Function, degree: 2)

## Relationships

- pipeline_visualizer_per_step_py_na_marker → pipeline_visualizer_per_step_py_save_json (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_attach_file_logger (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_draw_token_polygons (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_count_labels (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_save_json (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_save_image (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_box_area (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_rot (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_na_marker (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_tokens_from_ocr (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_make_tree (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_draw_boxes (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_build_db_parity_report (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_derive_yolo_report_from_dets (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_rect_intersection (calls)
- pipeline_visualizer_per_step_py_run_debug → pipeline_visualizer_per_step_py_detach_file_logger (calls)

