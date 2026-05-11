"""
core — Shared library for AHFL-Masking 1.1

Single source of truth for:
  - Configuration (core.config)
  - Database operations (core.db.*)
  - OCR & masking logic (core.ocr.*)
  - YOLO model management (core.models.*)
  - Utilities (core.utils.*)
  - Aadhaar side detection (core.classifiers)

All microservices import from this package instead of duplicating logic.
"""

# ── Configuration ──
from .config import (
    HOST,
    API_GATEWAY_PORT,
    MASKING_ENGINE_URL,
    OUTPUT_FOLDER,
    MODEL_MAIN,
    MODEL_BEST,
    MODEL_FRONT_BACK,
    TABLE_NAME,
    COMMIT_BATCH_SIZE,
    SKIP_KEYWORDS,
    GPU_MEMORY_FRACTION,
    GPU_WARMUP_ENABLED,
    ORIENTATION_ENABLED,
    ORIENTATION_EARLY_EXIT_CONF,
    ORIENTATION_ANGLES,
    LOG_LEVEL,
    PADDLE_MODEL_DIR,
    YOLO_MAIN_DILATE_ENABLED,
    setup_logging,
)

# ── Pipeline ──
from .pipeline import process_image

# ── Database (DynamoDB only) ──
from .db import get_dynamo_table, write_mask_log
from .db.log_writer import (
    bulk_write_logs,
    ensure_log_table,
    get_processed_paths,
)

# ── OCR & Masking ──
from .ocr import (
    find_aadhaar_patterns,
    mask_ocr_detections,
    mask_yolo_detections,
    merge_detections,
    yolo_results_to_detections,
    verhoeff_validate,
    adapt_paddle_result,
    get_texts_and_boxes,
    create_paddle_ocr,
    resize_image_for_ocr,
    scale_adapted_ocr_results,
)

# ── YOLO Models ──
from .models import (
    YOLORunner,
    get_yolo_main,
    get_yolo_best,
)

# ── Aadhaar Gate ──
from .aadhaar_gate import run_full_gate_scoring

# ── Classifiers ──
from .classifiers import detect_aadhaar_side, is_pan_card, is_aadhaar_card_confirmed

# ── Spatial ──
from .spatial import (
    is_inside_aadhaar_by_area,
    find_aadhaar_card_boxes,
    find_qr_boxes,
    compute_intersection_area,
    filter_dets_inside_box,
    map_dets_to_crop,
    map_crop_dets_to_full,
)

# ── Utilities ──
from .utils.counts import count_files_in_folder
from .utils.file_utils import (
    is_supported_file,
    pdf_to_images,
    images_to_pdf,
    validate_file_size,
    get_file_extension,
    ensure_output_dir,
    should_skip_file,
)

__all__ = [
    # Config
    "HOST",
    "API_GATEWAY_PORT",
    "MASKING_ENGINE_URL",
    "OUTPUT_FOLDER",
    "MODEL_MAIN",
    "MODEL_BEST",
    "MODEL_FRONT_BACK",
    "TABLE_NAME",
    "COMMIT_BATCH_SIZE",
    "SKIP_KEYWORDS",
    "GPU_MEMORY_FRACTION",
    "GPU_WARMUP_ENABLED",
    "ORIENTATION_ENABLED",
    "ORIENTATION_EARLY_EXIT_CONF",
    "ORIENTATION_ANGLES",
    "LOG_LEVEL",
    "PADDLE_MODEL_DIR",
    "setup_logging",
    # Pipeline
    "process_image",
    # Database
    "get_dynamo_table",
    "write_mask_log",
    "bulk_write_logs",
    "ensure_log_table",
    "get_processed_paths",
    # OCR & Masking
    "find_aadhaar_patterns",
    "mask_ocr_detections",
    "mask_yolo_detections",
    "merge_detections",
    "yolo_results_to_detections",
    "verhoeff_validate",
    "adapt_paddle_result",
    "get_texts_and_boxes",
    "create_paddle_ocr",
    "resize_image_for_ocr",
    "scale_adapted_ocr_results",
    # YOLO Models
    "YOLORunner",
    "get_yolo_main",
    "get_yolo_best",
    # Classifiers
    "detect_aadhaar_side",
    "is_pan_card",
    "is_aadhaar_card_confirmed",
    # Aadhaar Gate
    "run_full_gate_scoring",
    # Spatial
    "is_inside_aadhaar_by_area",
    "find_aadhaar_card_boxes",
    "find_qr_boxes",
    "compute_intersection_area",
    "filter_dets_inside_box",
    "map_dets_to_crop",
    "map_crop_dets_to_full",
    # Utilities
    "count_files_in_folder",
    "is_supported_file",
    "pdf_to_images",
    "images_to_pdf",
    "validate_file_size",
    "get_file_extension",
    "ensure_output_dir",
    "should_skip_file",
]
