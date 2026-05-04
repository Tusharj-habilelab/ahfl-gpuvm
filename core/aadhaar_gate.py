"""
aadhaar_gate.py — Aadhaar Gate for AHFL-Masking 1.1

Single-phase gate that runs ALL model inference per orientation angle:
  main.pt (greyscale+dilated) + front_back_detect.pt (greyscale) + best.pt (RGB crop)

Architecture:
  - Orientation calls run_full_gate_scoring() per angle
  - Returns (score, gate_result) — gate_result is COMPLETE, no second pass needed
  - Pipeline uses winner's gate_result directly for masking
  - Spatial QR filtering is NOT done here — moved to masking stage

Models used:
  main.pt: aadhaar, number, qr, number_anticlockwise, number_inverse, others
  front_back_detect.pt: Aadhaar, Front, Back, QR, Number, Other
  best.pt: is_number, is_number_masked, is_xx, is_qr, is_qr_masked

Preprocessing:
  main.pt: greyscale + dilation (trained on dilated greyscale)
  front_back_detect.pt: greyscale only (reuses same grey object)
  best.pt: RGB colour crop (trained on RGB)
"""

import cv2
import logging
from typing import Any, Dict, List, Tuple

import numpy as np

from core.models.yolo_runner import get_yolo_main, get_yolo_best
from core.classifiers import detect_aadhaar_side
from core.ocr.masking import yolo_results_to_detections, merge_detections
from core.spatial import (
    find_aadhaar_card_boxes,
    filter_dets_inside_box,
    map_crop_dets_to_full,
)

log = logging.getLogger(__name__)


def _preprocess_greyscale(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert BGR image to greyscale and dilated greyscale. Done ONCE per angle.

    Returns:
        (grey, dilated) — grey for front_back_detect.pt, dilated for main.pt.
    """
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(grey, kernel, iterations=1)
    return grey, dilated


def _process_single_aadhaar_crop(
    image: np.ndarray,
    aadhaar_box: List[float],
    filtered_dets: List[dict],
) -> Dict[str, Any]:
    """
    Run best.pt on a single Aadhaar card crop (RGB) and merge with main.pt dets.

    Args:
        image: Full BGR image (RGB — best.pt trained on colour).
        aadhaar_box: [x1, y1, x2, y2] in full-image coords.
        filtered_dets: main.pt+fb filtered detections (full-image coords).

    Returns:
        Dict with merged_dets (full-image coords) and crop_box.
    """
    x1, y1, x2, y2 = [int(c) for c in aadhaar_box]
    h, w = image.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    if x2 <= x1 or y2 <= y1:
        return {"merged_dets": [], "crop_box": aadhaar_box}

    crop = image[y1:y2, x1:x2]  # RGB crop — best.pt trained on colour
    crop_box = [x1, y1, x2, y2]

    yolo_best = get_yolo_best()
    results_best = yolo_best(crop, half=True)[0]
    dets_best_crop = yolo_results_to_detections(results_best, model_name="best")
    del results_best

    dets_best_full = map_crop_dets_to_full(dets_best_crop, crop_box)
    main_inside = filter_dets_inside_box(filtered_dets, crop_box)
    merged = merge_detections(main_inside, dets_best_full)

    return {
        "merged_dets": merged,
        "crop_box": crop_box,
    }


def run_full_gate_scoring(
    image: np.ndarray,
) -> Tuple[float, Dict[str, Any]]:
    """
    Full Aadhaar Gate: runs ALL 3 models and returns score + complete gate_result.

    Called by orientation loop for each candidate angle. The winning angle's
    gate_result is used directly by the pipeline — no second pass needed.

    Flow:
      1. Greyscale + dilation (once)
      2. main.pt(dilated) → detections
      3. front_back_detect.pt(grey) → filter/confirm
      4. Find Aadhaar card bboxes
      5. Per Aadhaar bbox: crop → best.pt(RGB) → merge
      6. Compute score + return gate_result

    Args:
        image: BGR numpy array (rotated to candidate angle).

    Returns:
        Tuple of (score, gate_result):
          score: float — higher = better Aadhaar detection at this angle.
          gate_result: dict with keys:
            - merged_dets: list of merged detection dicts (full-image coords)
            - aadhaar_boxes: list of Aadhaar card bboxes
            - aadhaar_crops: list of crop info dicts per card
            - fb_confirmed: bool
            - max_aadhaar_conf: float
    """
    # Step 1: Greyscale preprocessing (done ONCE, reused by main.pt and fb)
    grey, dilated = _preprocess_greyscale(image)

    # Step 2: Run main.pt on dilated greyscale
    yolo_main = get_yolo_main()
    results_main = yolo_main(dilated, half=True)[0]
    main_dets = yolo_results_to_detections(results_main, model_name="main")
    del results_main

    # Step 3: Run front_back_detect.pt filter (reuses grey — no duplicate cvtColor)
    coordinates = [d["box"] for d in main_dets]
    labels = [d["label"] for d in main_dets]
    confs = [d["conf"] for d in main_dets]

    f_coords, f_labels, f_confs = detect_aadhaar_side(
        grey, coordinates, labels, confs
    )
    filtered_dets = [
        {"box": c, "label": l, "conf": cf, "model": "main+fb"}
        for c, l, cf in zip(f_coords, f_labels, f_confs)
    ]
    del grey, dilated  # free full-resolution arrays (called up to 8× in orientation loop)

    # Compute score from confirmed Aadhaar detections
    aadhaar_confs = [
        d["conf"] for d in filtered_dets
        if d.get("label", "").lower() == "aadhaar"
    ]
    fb_confirmed = len(aadhaar_confs) > 0
    max_aadhaar_conf = max(aadhaar_confs) if aadhaar_confs else 0.0

    if aadhaar_confs:
        score = max_aadhaar_conf + min(len(aadhaar_confs), 3) * 0.05 + 0.1
    else:
        raw_aadhaar_confs = [
            d["conf"] for d in main_dets
            if d.get("label", "").lower() == "aadhaar"
        ]
        if raw_aadhaar_confs:
            score = max(raw_aadhaar_confs) * 0.5
        else:
            score = len(main_dets) * 0.01

    # Step 4: Find Aadhaar card bboxes
    aadhaar_boxes = find_aadhaar_card_boxes(filtered_dets)

    # Step 5: Run best.pt on each Aadhaar crop (RGB)
    if aadhaar_boxes:
        all_merged = []
        aadhaar_crops = []
        for abox in aadhaar_boxes:
            crop_result = _process_single_aadhaar_crop(
                image, abox, filtered_dets
            )
            all_merged.extend(crop_result["merged_dets"])
            aadhaar_crops.append(crop_result)

        # Add non-Aadhaar dets outside any crop
        all_crop_boxes = [c["crop_box"] for c in aadhaar_crops]
        for det in filtered_dets:
            if det.get("label", "").lower() == "aadhaar":
                continue
            inside_any = any(
                len(filter_dets_inside_box([det], cbox)) > 0
                for cbox in all_crop_boxes
            )
            if not inside_any:
                all_merged.append(det)
    else:
        # No Aadhaar cards — fallback: best.pt on full image (RGB)
        yolo_best = get_yolo_best()
        results_best = yolo_best(image, half=True)[0]
        dets_best = yolo_results_to_detections(results_best, model_name="best")
        del results_best
        all_merged = merge_detections(filtered_dets, dets_best)
        aadhaar_crops = []

    gate_result = {
        "merged_dets": all_merged,
        "aadhaar_boxes": aadhaar_boxes,
        "aadhaar_crops": aadhaar_crops,
        "fb_confirmed": fb_confirmed,
        "max_aadhaar_conf": max_aadhaar_conf,
    }

    # Extract best.pt number and QR confidence for composite scoring
    # Used by orientation angle selection to include target evidence
    best_number_confs = [
        d["conf"] for d in all_merged
        if "number" in d.get("label", "").lower() and d.get("model") == "best"
    ]
    best_qr_confs = [
        d["conf"] for d in all_merged
        if "qr" in d.get("label", "").lower() and d.get("model") == "best"
    ]
    
    gate_result["best_number_conf"] = max(best_number_confs) if best_number_confs else 0.0
    gate_result["best_qr_conf"] = max(best_qr_confs) if best_qr_confs else 0.0

    return score, gate_result
