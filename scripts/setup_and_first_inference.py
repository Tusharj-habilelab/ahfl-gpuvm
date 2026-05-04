#!/usr/bin/env python3
"""
setup_and_first_inference.py — One-time setup: download PaddleOCR models + run first inference.

Run this ONCE with internet access to:
  1. Download PaddleOCR models into services/masking-engine/models/paddleocr/
  2. Verify all YOLO models are present
  3. Run the full masking pipeline on a test image
  4. Save the masked output to output/masked/

After this script completes, the paddleocr/ folder is populated and the service
will work offline on the GPU instance without re-downloading anything.

Usage:
  cd /path/to/ahfl-working-Gpu
  python scripts/setup_and_first_inference.py
  python scripts/setup_and_first_inference.py --image /path/to/other.jpg
"""

import os
import sys
import gc
import argparse
import logging
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Resolve absolute paths relative to project root
# ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR   = PROJECT_ROOT / "services" / "masking-engine" / "models"
PADDLE_DIR   = MODELS_DIR / "paddleocr"
OUTPUT_DIR   = PROJECT_ROOT / "output" / "masked"

# ─────────────────────────────────────────────────────────────
# Set env vars BEFORE any import that triggers model loading.
# PaddleOCR reads PADDLE_MODEL_DIR at __init__ time via create_paddle_ocr().
# ─────────────────────────────────────────────────────────────
os.environ["PADDLE_MODEL_DIR"] = str(PADDLE_DIR)
os.environ["MODEL_MAIN"]       = str(MODELS_DIR / "main.pt")
os.environ["MODEL_BEST"]       = str(MODELS_DIR / "best.pt")
os.environ["MODEL_FRONT_BACK"] = str(MODELS_DIR / "front_back_detect.pt")
os.environ["MODEL_YOLO_N"]     = str(MODELS_DIR / "yolov8n.pt")

# Add project root so `import core` resolves correctly
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "masking-engine"))

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("setup")


# ─────────────────────────────────────────────────────────────
# Step 1 — Verify YOLO models are on disk
# ─────────────────────────────────────────────────────────────

def check_yolo_models():
    required = {
        "main.pt":              os.environ["MODEL_MAIN"],
        "best.pt":              os.environ["MODEL_BEST"],
        "front_back_detect.pt": os.environ["MODEL_FRONT_BACK"],
    }
    missing = [name for name, path in required.items() if not Path(path).exists()]
    if missing:
        log.error(f"Missing YOLO models: {', '.join(missing)}")
        log.error(f"Place them in: {MODELS_DIR}")
        sys.exit(1)
    log.info(f"✓ YOLO models verified in {MODELS_DIR}")


# ─────────────────────────────────────────────────────────────
# Step 2 — Initialize PaddleOCR (downloads models on first run)
# ─────────────────────────────────────────────────────────────

def init_paddle_ocr():
    for sub in ("det", "rec", "cls", "doc_orientation"):
        (PADDLE_DIR / sub).mkdir(parents=True, exist_ok=True)

    log.info(f"Initializing PaddleOCR → {PADDLE_DIR}")
    log.info("  First run downloads ~200 MB of models. Please wait...")

    from core.ocr.paddle import create_paddle_ocr
    ocr = create_paddle_ocr()

    log.info("✓ PaddleOCR initialized — models saved to disk")
    return ocr


# ─────────────────────────────────────────────────────────────
# Step 3 — Run full masking pipeline on the test image
# ─────────────────────────────────────────────────────────────

def run_inference(image_path: Path, ocr) -> Path:
    import cv2

    from core.models import get_yolo_main, get_yolo_best
    from core.ocr.masking import (
        yolo_results_to_detections,
        merge_detections,
        mask_yolo_detections,
        find_aadhaar_patterns,
        mask_ocr_detections,
    )
    from core.ocr.ocr_adapter import adapt_paddle_result, get_texts_and_boxes
    from core.ocr.paddle import resize_image_for_ocr, scale_adapted_ocr_results
    from core.classifiers import detect_aadhaar_side

    log.info("Loading YOLO models...")
    yolo_main = get_yolo_main()
    yolo_best = get_yolo_best()
    log.info("✓ YOLO models loaded")

    log.info(f"Reading image: {image_path}")
    image = cv2.imread(str(image_path))
    if image is None:
        log.error(f"Cannot read image: {image_path}")
        sys.exit(1)

    # ── YOLO detection ──
    log.info("Running YOLO detection...")
    results_main = yolo_main(image)[0]
    results_best = yolo_best(image)[0]

    dets_main = yolo_results_to_detections(results_main, model_name="main")
    dets_best = yolo_results_to_detections(results_best, model_name="best")
    merged    = merge_detections(dets_main, dets_best)
    del results_main, results_best

    coordinates = [d["box"]   for d in merged]
    labels      = [d["label"] for d in merged]
    confs       = [d["conf"]  for d in merged]

    f_coords, f_labels, f_confs = detect_aadhaar_side(image, coordinates, labels, confs)
    filtered = [
        {"box": c, "label": l, "conf": cf, "model": "merged"}
        for c, l, cf in zip(f_coords, f_labels, f_confs)
    ]
    del dets_main, dets_best, merged

    image, yolo_report = mask_yolo_detections(image, filtered)
    log.info(f"  YOLO report: {yolo_report}")

    # ── PaddleOCR detection ──
    log.info("Running PaddleOCR...")
    ocr_image, scale = resize_image_for_ocr(image)
    try:
        ocr_results = ocr.ocr(ocr_image)
        adapted = adapt_paddle_result(ocr_results) if (ocr_results and ocr_results[0]) else []
        adapted = scale_adapted_ocr_results(adapted, scale)
    except Exception as e:
        log.warning(f"OCR error (non-fatal): {e}")
        adapted = []

    texts, boxes, confidences = get_texts_and_boxes(adapted)
    tokens_list    = [{"text": t, "coordinates": b, "confidence": c}
                      for t, b, c in zip(texts, boxes, confidences)]
    detected_words = find_aadhaar_patterns(tokens_list)
    image          = mask_ocr_detections(image, detected_words, tokens_list)
    log.info(f"  OCR patterns masked: {len(detected_words)}")

    # ── Save output ──
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"masked_{image_path.name}"
    cv2.imwrite(str(output_path), image)
    log.info(f"✓ Masked image saved → {output_path}")

    del image, adapted, tokens_list, detected_words
    gc.collect()

    return output_path


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download PaddleOCR models and run first masking inference"
    )
    parser.add_argument(
        "--image",
        default=str(PROJECT_ROOT / "aadhaar_images__o_aadhaar12.jpeg"),
        help="Path to test image (default: aadhaar_images__o_aadhaar12.jpeg in project root)",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        log.error(f"Image not found: {image_path}")
        sys.exit(1)

    log.info("=" * 60)
    log.info("AHFL Masking Engine — Setup & First Inference")
    log.info("=" * 60)
    log.info(f"Project root  : {PROJECT_ROOT}")
    log.info(f"YOLO models   : {MODELS_DIR}")
    log.info(f"PaddleOCR dir : {PADDLE_DIR}")
    log.info(f"Output dir    : {OUTPUT_DIR}")
    log.info(f"Test image    : {image_path}")
    log.info("=" * 60)

    check_yolo_models()
    ocr    = init_paddle_ocr()
    output = run_inference(image_path, ocr)

    log.info("=" * 60)
    log.info("Setup complete.")
    log.info(f"  PaddleOCR models cached at : {PADDLE_DIR}")
    log.info(f"  Masked output saved at     : {output}")
    log.info("  The GPU instance can now run offline — no internet needed.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
