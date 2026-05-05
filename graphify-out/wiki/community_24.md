# Community 24: _normalize_bbox()

**Members:** 6

## Nodes

- **ocr_adapter** (`core_ocr_ocr_adapter_py`, File, degree: 5)
- **adapt_paddle_result()** (`core_ocr_ocr_adapter_py_adapt_paddle_result`, Function, degree: 3)
- **_append_v3_result()** (`core_ocr_ocr_adapter_py_append_v3_result`, Function, degree: 3)
- **get_texts_and_boxes()** (`core_ocr_ocr_adapter_py_get_texts_and_boxes`, Function, degree: 2)
- **logging** (`core_ocr_ocr_adapter_py_import_logging`, Module, degree: 1)
- **_normalize_bbox()** (`core_ocr_ocr_adapter_py_normalize_bbox`, Function, degree: 2)

## Relationships

- core_ocr_ocr_adapter_py → core_ocr_ocr_adapter_py_import_logging (imports)
- core_ocr_ocr_adapter_py → core_ocr_ocr_adapter_py_normalize_bbox (defines)
- core_ocr_ocr_adapter_py → core_ocr_ocr_adapter_py_append_v3_result (defines)
- core_ocr_ocr_adapter_py → core_ocr_ocr_adapter_py_adapt_paddle_result (defines)
- core_ocr_ocr_adapter_py → core_ocr_ocr_adapter_py_get_texts_and_boxes (defines)
- core_ocr_ocr_adapter_py_append_v3_result → core_ocr_ocr_adapter_py_normalize_bbox (calls)
- core_ocr_ocr_adapter_py_adapt_paddle_result → core_ocr_ocr_adapter_py_append_v3_result (calls)
- core_ocr_ocr_adapter_py_get_texts_and_boxes → core_ocr_ocr_adapter_py_adapt_paddle_result (calls)

