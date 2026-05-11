# Migrated from: detect_aadhaar_side.py (AHFL-Masking 1.0)
# Role: YOLO-based Aadhaar front/back classifier. Promoted to core/ so both
#        the masking-engine service and any future services can use it.
"""
classifiers.py — YOLO-based document side classifier for AHFL-Masking 1.1.

Filters YOLO detections to keep only those whose cropped region
is confirmed as Aadhaar front or back by a secondary classifier model.
"""

import os
import re
import logging
import threading
import cv2
import numpy as np
import torch
from typing import List, Tuple
from ultralytics import YOLO
from dotenv import load_dotenv
from core.config import PVC_PERSON_CONFIDENCE_THRESHOLD

load_dotenv()

log = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()
_person_model = None
_person_model_lock = threading.Lock()
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# PAN card regex: 5 uppercase letters + 4 digits + 1 uppercase letter
_PAN_PATTERN = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")


def _get_classifier():
    """Lazy-load the front/back classifier model (avoids loading at import time)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                model_path = os.environ.get("MODEL_FRONT_BACK", "models/front_back_detect.pt")
                log.info(f"Loading front/back classifier from {model_path} on {_DEVICE}")
                _model = YOLO(model_path).to(_DEVICE)
                log.info("\u2713 front/back classifier loaded")
    return _model


def _get_person_model():
    """Lazy-load yolov8n for person detection on PVC Aadhaar cards."""
    global _person_model
    if _person_model is None:
        with _person_model_lock:
            if _person_model is None:
                model_path = os.environ.get("MODEL_YOLO_N", "models/yolov8n.pt")
                log.info(f"Loading person detector (yolov8n) from {model_path} on {_DEVICE}")
                _person_model = YOLO(model_path).to(_DEVICE)
                log.info("\u2713 person detector loaded")
    return _person_model


def detect_aadhaar_side(image, coordinates, labels, conf, return_metadata: bool = False):
    """
    Filter detections — keep only those whose crop the classifier confirms
    as Aadhaar (class 0), front (class 1), or back (class 2).

    Passes numpy arrays directly to YOLO (no disk I/O).

    Args:
        image:       np.ndarray — greyscale image (from gate's single cvtColor)
                     or BGR image (backwards compatible — will convert if needed)
        coordinates: list of [x1, y1, x2, y2]
        labels:      list of str — YOLO label per detection
        conf:        list of float — confidence per detection
        return_metadata: if True, return metadata list with fb_classes and fb_pvc_detected

        Returns:
                If return_metadata=False: filtered_coords, filtered_labels, filtered_conf
                If return_metadata=True: filtered_coords, filtered_labels, filtered_conf, filtered_metadata
                    where metadata contains {"fb_classes": [...], "fb_pvc_detected": bool}
    """
    model = _get_classifier()

    # Determine if image is already greyscale (gate passes grey)
    is_greyscale = len(image.shape) == 2 or (len(image.shape) == 3 and image.shape[2] == 1)

    # Build list of valid crops and their original indices
    crops = []
    crop_indices = []
    for i, coord in enumerate(coordinates):
        x1, y1, x2, y2 = map(int, coord)
        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        bgr_crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR) if is_greyscale else crop
        crops.append(bgr_crop)
        crop_indices.append(i)

    if not crops:
        if return_metadata:
            return [], [], [], []
        return [], [], []

    # Batch inference — single GPU call for all crops
    batch_results = model(crops)

    filtered_coords = []
    filtered_labels = []
    filtered_conf = []
    filtered_metadata = []

    for result, orig_idx in zip(batch_results, crop_indices):
        detected_classes = []
        if result.boxes is not None:
            detected_classes = [int(c) for c in result.boxes.cls.tolist()]

        lbl = labels[orig_idx].lower()
        if (any(c in (0, 1, 2) for c in detected_classes) and lbl == "aadhaar") or lbl != "aadhaar":
            filtered_coords.append(coordinates[orig_idx])
            filtered_labels.append(labels[orig_idx])
            filtered_conf.append(conf[orig_idx])
            if return_metadata:
                filtered_metadata.append({
                    "fb_classes": detected_classes,
                    "fb_pvc_detected": lbl == "aadhaar" and 2 in detected_classes,
                })

    pvc_count = sum(1 for m in filtered_metadata if m.get("fb_pvc_detected")) if return_metadata else 0
    log.info(f"detect_aadhaar_side: in={len(coordinates)} → out={len(filtered_coords)} pvc_detected={pvc_count}")
    if return_metadata:
        return filtered_coords, filtered_labels, filtered_conf, filtered_metadata
    return filtered_coords, filtered_labels, filtered_conf


def is_pan_card(ocr_texts: List[str]) -> bool:
    """
    Detect if OCR text indicates a PAN card (not Aadhaar).

    Multi-signal approach to avoid false positives from names like Pankaj/Pandey:
    Requires 2+ signals from:
      - INCOME TAX DEPARTMENT keyword (2 points)
      - PERMANENT ACCOUNT NUMBER phrase (2 points)
      - PAN regex pattern: [A-Z]{5}[0-9]{4}[A-Z] (1 point)
      - Word-boundary "PAN" match (1 point)

    Threshold: 2+ signals required to confirm PAN card.

    Args:
        ocr_texts: List of OCR-extracted text strings.

    Returns:
        True if 2+ PAN indicators found.
    """
    combined = " ".join(ocr_texts)
    combined_upper = combined.upper()

    signal_count = 0

    if "INCOME TAX DEPARTMENT" in combined_upper:
        signal_count += 2

    if "PERMANENT ACCOUNT NUMBER" in combined_upper:
        signal_count += 2

    if _PAN_PATTERN.search(combined_upper):
        signal_count += 1

    if re.search(r'\bPAN\b', combined_upper):
        signal_count += 1

    result = signal_count >= 2
    if result:
        log.info(f"is_pan_card: PAN detected (signals={signal_count}) — will SKIP masking")
    return result


def normalize_aadhaar_keyword(text: str) -> str:
    """
    Normalize Aadhaar-related keyword for robust matching.
    
    Handles OCR variants like:
      - "Your Aadhaar No"
      - "Your Aadhaar No."
      - "Your Aadhaar No. :"
      - "YOUR AADHAAR NO"
      - Extra spaces and punctuation
    
    Args:
        text: Raw text string
    
    Returns:
        Normalized string (uppercase, no punctuation, collapsed whitespace)
    """
    import re
    # Remove common punctuation
    text = re.sub(r'[.:;,\-_(){}[\]]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Uppercase and strip
    return text.upper().strip()


def is_aadhaar_card_confirmed(ocr_texts: List[str]) -> bool:
    """
    Confirm that OCR text from a card crop contains Aadhaar-specific keywords.

    Only used on the card path (when YOLO detected an Aadhaar bbox).
    If confirmed, PAN check is skipped for this crop.

    Checks for normalized variants of:
      - "Your Aadhaar No" (and punctuation variants)
    
    Uses normalization to handle OCR noise and formatting differences.
    """
    combined = " ".join(ocr_texts)
    normalized = normalize_aadhaar_keyword(combined)
    
    # Check for normalized Aadhaar card keyword
    target_keywords = [
        "YOUR AADHAAR NO",
        "YOUR AADHAR NO",  # Common spelling variant
    ]
    
    for keyword in target_keywords:
        if keyword in normalized:
            log.info(f"is_aadhaar_card_confirmed: confirmed via keyword '{keyword}'")
            return True

    log.debug("is_aadhaar_card_confirmed: not confirmed")
    return False


def mask_pvc_aadhaar(image: np.ndarray, aadhaar_crops: List[dict]) -> Tuple[np.ndarray, dict]:
    """
    Mask person photos on PVC Aadhaar cards using yolov8n.pt person detection.

    Detects the two person regions (main + ghost photo) on each Aadhaar card
    and masks the smaller one with a black rectangle.

    Args:
        image: Full BGR image (already at winning orientation from gate).
        aadhaar_crops: List of dicts from gate_result["aadhaar_crops"],
                       each containing "crop_box": [x1, y1, x2, y2].
                       If "fb_pvc_detected" is present, only True crops are processed.

    Returns:
        Tuple of (modified_image, stats_dict) where:
        - modified_image: Image with person photos masked
        - stats_dict: {"pvc_cards_processed": int, "pvc_cards_masked": int}
    """
    if not aadhaar_crops:
        return image, {"pvc_cards_processed": 0, "pvc_cards_masked": 0}

    # Filter to PVC-detected crops if metadata available, else fallback to all
    has_pvc_flags = any("fb_pvc_detected" in crop_info for crop_info in aadhaar_crops)
    pvc_candidate_crops = [
        crop_info for crop_info in aadhaar_crops
        if not has_pvc_flags or crop_info.get("fb_pvc_detected", False)
    ]

    if not pvc_candidate_crops:
        return image, {"pvc_cards_processed": 0, "pvc_cards_masked": 0}

    person_model = _get_person_model()
    h, w = image.shape[:2]
    pvc_cards_processed = 0
    pvc_cards_masked = 0

    for crop_info in pvc_candidate_crops:
        crop_box = crop_info.get("crop_box")
        if crop_box is None:
            continue

        pvc_cards_processed += 1
        x1, y1, x2, y2 = map(int, crop_box)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            continue

        aadhaar_region = image[y1:y2, x1:x2]
        blurred = cv2.GaussianBlur(aadhaar_region, (3, 3), 0)

        person_coordinates = []
        try:
            results = person_model(blurred)
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        confidence = float(box.conf[0])
                        if class_id == 0 and confidence >= PVC_PERSON_CONFIDENCE_THRESHOLD:
                            person_coordinates.append(box.xyxy[0].tolist())
        except Exception as e:
            log.warning(f"PVC masking person detection failed: {e}")
            continue

        if len(person_coordinates) == 2:
            px11, py11, px12, py12 = map(int, person_coordinates[0])
            px21, py21, px22, py22 = map(int, person_coordinates[1])

            area1 = abs(px12 - px11) * abs(py12 - py11)
            area2 = abs(px22 - px21) * abs(py22 - py21)

            if area1 > area2:
                px22 = int(px22 + ((px22 - px21) / 10))
                py22 = int(py22 + ((py22 - py21) / 10))
                cv2.rectangle(aadhaar_region, (px21, py21), (px22, py22), (0, 0, 0), -1)
                log.debug(f"PVC masking: masked smaller person at ({px21},{py21})-({px22},{py22})")
            else:
                px12 = int(px12 + ((px12 - px11) / 10))
                py12 = int(py12 + ((py12 - py11) / 10))
                cv2.rectangle(aadhaar_region, (px11, py11), (px12, py12), (0, 0, 0), -1)
                log.debug(f"PVC masking: masked smaller person at ({px11},{py11})-({px12},{py12})")

            image[y1:y2, x1:x2] = aadhaar_region
            pvc_cards_masked += 1

    return image, {"pvc_cards_processed": pvc_cards_processed, "pvc_cards_masked": pvc_cards_masked}
