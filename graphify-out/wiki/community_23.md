# Community 23: levenshtein_score()

**Members:** 7

## Nodes

- **cosine_similarity()** (`core_ocr_masking_py_cosine_similarity`, Function, degree: 2)
- **extract_number_coordinates()** (`core_ocr_masking_py_extract_number_coordinates`, Function, degree: 2)
- **extract_target_coordinates()** (`core_ocr_masking_py_extract_target_coordinates`, Function, degree: 2)
- **find_aadhaar_patterns()** (`core_ocr_masking_py_find_aadhaar_patterns`, Function, degree: 8)
- **is_four_digit_number()** (`core_ocr_masking_py_is_four_digit_number`, Function, degree: 2)
- **is_twelve_digit_number()** (`core_ocr_masking_py_is_twelve_digit_number`, Function, degree: 2)
- **levenshtein_score()** (`core_ocr_masking_py_levenshtein_score`, Function, degree: 2)

## Relationships

- core_ocr_masking_py_find_aadhaar_patterns → core_ocr_masking_py_is_four_digit_number (calls)
- core_ocr_masking_py_find_aadhaar_patterns → core_ocr_masking_py_is_twelve_digit_number (calls)
- core_ocr_masking_py_find_aadhaar_patterns → core_ocr_masking_py_cosine_similarity (calls)
- core_ocr_masking_py_find_aadhaar_patterns → core_ocr_masking_py_levenshtein_score (calls)
- core_ocr_masking_py_find_aadhaar_patterns → core_ocr_masking_py_extract_number_coordinates (calls)
- core_ocr_masking_py_find_aadhaar_patterns → core_ocr_masking_py_extract_target_coordinates (calls)

