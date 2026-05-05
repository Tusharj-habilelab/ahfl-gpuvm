"""
config.py — Centralized configuration for AHFL-Masking 1.1

Loads all environment variables and provides defaults.
Single source of truth for config across all services.
"""

import os
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed; rely on environment variables set directly

# ────────────────────────────────────────────────────────
# API Gateway Configuration
# ────────────────────────────────────────────────────────

HOST = os.environ.get("HOST", "http://localhost:8000")
API_GATEWAY_PORT = int(os.environ.get("API_GATEWAY_PORT", 8000))
MASKING_ENGINE_URL = os.environ.get("MASKING_ENGINE_URL", "http://masking-engine:8001")
AUTHORIZED_KEYS_PATH = os.environ.get("AUTHORIZED_KEYS_PATH", "config/authorized-keys.txt")

# ────────────────────────────────────────────────────────
# Masking Engine Configuration
# ────────────────────────────────────────────────────────

MASKING_ENGINE_PORT = int(os.environ.get("MASKING_ENGINE_PORT", 8001))
OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", "./output/masked")

# YOLO Model Paths
MODEL_MAIN = os.environ.get("MODEL_MAIN", "models/main.pt")
MODEL_BEST = os.environ.get("MODEL_BEST", "models/best.pt")
MODEL_FRONT_BACK = os.environ.get("MODEL_FRONT_BACK", "models/front_back_detect.pt")
MODEL_YOLO_N = os.environ.get("MODEL_YOLO_N", "models/yolov8n.pt")

# PaddleOCR Model Path — models download here on first run, reused offline after
PADDLE_MODEL_DIR = os.environ.get("PADDLE_MODEL_DIR", "models/paddleocr")

# File constraints
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", 15 * 1024 * 1024))  # 15 MB — matches MAX_S3_FILE_SIZE in batch.py
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# ────────────────────────────────────────────────────────
# GPU Configuration
# ────────────────────────────────────────────────────────

# Single source of truth — engine.py, yolo_runner.py, paddle.py, batch.py all
# import this so the default can never diverge across services.
GPU_ENABLED = os.environ.get("GPU_ENABLED", "true").lower() == "true"
GPU_MEMORY_FRACTION = float(os.environ.get("TORCH_CUDA_MAX_MEMORY_FRAC", "0.7"))
GPU_WARMUP_ENABLED = os.environ.get("GPU_WARMUP", "true").lower() == "true"

# ────────────────────────────────────────────────────────
# YOLO Preprocessing Configuration
# ────────────────────────────────────────────────────────

# main.pt greyscale preprocessing: whether to dilate edges for better card detection
# Set to "false" for undilated greyscale (faster, less preprocessing overhead).
# Set to "true" to dilate greyscale (thickens card edges, may improve faded card detection).
# Default: false (no dilation) — model receives undilated greyscale-as-BGR
YOLO_MAIN_DILATE_ENABLED = os.environ.get("YOLO_MAIN_DILATE_ENABLED", "false").lower() == "true"

# ────────────────────────────────────────────────────────
# Orientation Configuration
# ────────────────────────────────────────────────────────

ORIENTATION_ENABLED = os.environ.get("ORIENTATION_ENABLED", "true").lower() == "true"
ORIENTATION_EARLY_EXIT_CONF = float(os.environ.get("ORIENTATION_EARLY_EXIT_CONF", "0.75"))
ORIENTATION_ANGLES = [
    int(a) for a in os.environ.get("ORIENTATION_ANGLES", "0,45,90,135,180,225,270,315").split(",")
]

# ────────────────────────────────────────────────────────
# Shared Pipeline Configuration
# ────────────────────────────────────────────────────────

SKIP_KEYWORDS = frozenset({
    "statement",
    "screening",
    "sampling",
    "bharatpe",
    "phonepe",
    "espay",
})

BATCH_PATH_SKIP_KEYWORDS = tuple(
    kw.strip().lower()
    for kw in os.environ.get(
        "BATCH_PATH_SKIP_KEYWORDS",
        "property,credit,bureau,sampling,screening,banking,epfo,tereport,estimate,location,sketch,cersai",
    ).split(",")
    if kw.strip()
)

# ────────────────────────────────────────────────────────────
# Router Configuration
# ────────────────────────────────────────────────────────────

ROUTER_ENABLED = os.environ.get("ROUTER_ENABLED", "true").lower() == "true"
ROUTER_CONFIDENCE_THRESHOLD = float(os.environ.get("ROUTER_CONFIDENCE_THRESHOLD", "0.55"))

ROUTER_OCR_LITE_MAX_TOKENS = int(os.environ.get("ROUTER_OCR_LITE_MAX_TOKENS", "30"))
ROUTER_OCR_LITE_MAX_SIDE = int(os.environ.get("ROUTER_OCR_LITE_MAX_SIDE", "800"))
ROUTER_CARD_TOKEN_MAX = int(os.environ.get("ROUTER_CARD_TOKEN_MAX", "50"))
ROUTER_FORM_TOKEN_MIN = int(os.environ.get("ROUTER_FORM_TOKEN_MIN", "80"))
ROUTER_TABLE_SIGNAL_MIN = int(os.environ.get("ROUTER_TABLE_SIGNAL_MIN", "2"))
ROUTER_BIAS_RATIO = float(os.environ.get("ROUTER_BIAS_RATIO", "1.5"))
ROUTER_CARD_CONF_DIVISOR = float(os.environ.get("ROUTER_CARD_CONF_DIVISOR", "5.0"))
ROUTER_FORM_CONF_DIVISOR = float(os.environ.get("ROUTER_FORM_CONF_DIVISOR", "6.0"))
ROUTER_MIXED_CONFIDENCE = float(os.environ.get("ROUTER_MIXED_CONFIDENCE", "0.3"))

# Composite scoring thresholds for orientation
ORIENTATION_TARGET_THRESHOLD = float(os.environ.get("ORIENTATION_TARGET_THRESHOLD", "0.7"))
ORIENTATION_STRONG_THRESHOLD = float(os.environ.get("ORIENTATION_STRONG_THRESHOLD", "0.75"))

# OCR + detection thresholds
PADDLE_OCR_MAX_SIDE = max(640, int(os.environ.get("PADDLE_OCR_MAX_SIDE", "1600")))
PVC_PERSON_CONFIDENCE_THRESHOLD = float(os.environ.get("PVC_PERSON_CONFIDENCE_THRESHOLD", "0.5"))
PVC_MAX_ROTATIONS = int(os.environ.get("PVC_MAX_ROTATIONS", "2"))

# ────────────────────────────────────────────────────────
# Batch Processor Configuration
# ────────────────────────────────────────────────────────

BATCH_PROCESSOR_PORT = int(os.environ.get("BATCH_PROCESSOR_PORT", 8002))
TABLE_NAME = os.environ.get("TABLE_NAME", "ahfl_processed_data")
COMMIT_BATCH_SIZE = int(os.environ.get("COMMIT_BATCH_SIZE", 20))
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "500"))
PDF_CHUNK_SIZE = int(os.environ.get("PDF_CHUNK_SIZE", "10"))
MAX_S3_FILE_SIZE = int(os.environ.get("MAX_S3_FILE_SIZE", str(15 * 1024 * 1024)))
STALE_PROCESSING_HOURS = int(os.environ.get("STALE_PROCESSING_HOURS", "24"))

# ────────────────────────────────────────────────────────
# Logging Configuration
# ────────────────────────────────────────────────────────

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def validate_required_env_vars() -> None:
    """Raise RuntimeError if required env vars are missing at startup."""
    required = ["TABLE_NAME", "AWS_REGION", "RAW_BUCKET", "MASKED_BUCKET"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Set them in docker-compose.yml or environment."
        )


def setup_logging(service_name: str) -> logging.Logger:
    """
    Configure and return a logger for a service.

    Args:
        service_name: Name of the service (e.g., "api-gateway", "masking-engine")

    Returns:
        Configured logger instance
    """
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    return logging.getLogger(service_name)
