# OCR module for AHFL-Masking 1.1
from .masking import (
    find_aadhaar_patterns,
    mask_ocr_detections,
    mask_yolo_detections,
    merge_detections,
    yolo_results_to_detections,
    verhoeff_validate,
    is_valid_aadhaar_number,
    compute_digit_mask_region,
    cosine_similarity,
    levenshtein_score,
)
from .ocr_adapter import adapt_paddle_result, get_texts_and_boxes
from .paddle import create_paddle_ocr, resize_image_for_ocr, scale_adapted_ocr_results

__all__ = [
    "find_aadhaar_patterns",
    "mask_ocr_detections",
    "mask_yolo_detections",
    "merge_detections",
    "yolo_results_to_detections",
    "verhoeff_validate",
    "is_valid_aadhaar_number",
    "compute_digit_mask_region",
    "cosine_similarity",
    "levenshtein_score",
    "adapt_paddle_result",
    "get_texts_and_boxes",
    "create_paddle_ocr",
    "resize_image_for_ocr",
    "scale_adapted_ocr_results",
]
