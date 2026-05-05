# Community 19: map_dets_to_crop()

**Members:** 9

## Nodes

- **spatial** (`core_spatial_py`, File, degree: 8)
- **compute_intersection_area()** (`core_spatial_py_compute_intersection_area`, Function, degree: 3)
- **filter_dets_inside_box()** (`core_spatial_py_filter_dets_inside_box`, Function, degree: 2)
- **find_aadhaar_card_boxes()** (`core_spatial_py_find_aadhaar_card_boxes`, Function, degree: 1)
- **find_qr_boxes()** (`core_spatial_py_find_qr_boxes`, Function, degree: 1)
- **typing.List** (`core_spatial_py_import_typing_list`, Module, degree: 1)
- **is_inside_aadhaar_by_area()** (`core_spatial_py_is_inside_aadhaar_by_area`, Function, degree: 2)
- **map_crop_dets_to_full()** (`core_spatial_py_map_crop_dets_to_full`, Function, degree: 1)
- **map_dets_to_crop()** (`core_spatial_py_map_dets_to_crop`, Function, degree: 1)

## Relationships

- core_spatial_py → core_spatial_py_import_typing_list (imports)
- core_spatial_py → core_spatial_py_compute_intersection_area (defines)
- core_spatial_py → core_spatial_py_is_inside_aadhaar_by_area (defines)
- core_spatial_py → core_spatial_py_find_aadhaar_card_boxes (defines)
- core_spatial_py → core_spatial_py_find_qr_boxes (defines)
- core_spatial_py → core_spatial_py_filter_dets_inside_box (defines)
- core_spatial_py → core_spatial_py_map_dets_to_crop (defines)
- core_spatial_py → core_spatial_py_map_crop_dets_to_full (defines)
- core_spatial_py_is_inside_aadhaar_by_area → core_spatial_py_compute_intersection_area (calls)
- core_spatial_py_filter_dets_inside_box → core_spatial_py_compute_intersection_area (calls)

