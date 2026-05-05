"""
pipeline.py — Unified masking pipeline for AHFL-Masking 1.1.

Lane-based flow:
  - form: OCR-first path, no YOLO gate/orientation sweep
  - card: full orientation + gate + verification-before-masking
  - uncertain: safe fallback to card path
"""

import gc
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from core.aadhaar_gate import run_full_gate_scoring
from core.classifiers import is_aadhaar_card_confirmed, is_pan_card, mask_pvc_aadhaar
from core.config import (
    ROUTER_CONFIDENCE_THRESHOLD,
    ROUTER_ENABLED,
    SKIP_KEYWORDS,
)
from core.ocr.masking import find_aadhaar_patterns, mask_ocr_detections, mask_yolo_detections
from core.ocr.ocr_adapter import adapt_paddle_result, get_texts_and_boxes
from core.ocr.paddle import (
    create_paddle_ocr,
    get_doc_orientation_model,
    resize_image_for_ocr,
    run_ocr_lite_for_routing,
    scale_adapted_ocr_results,
)
from core.router import classify_document_lane
from core.utils.angle_detector import find_best_orientation

log = logging.getLogger(__name__)

_ocr_instance = None
_ocr_lock = threading.Lock()


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        with _ocr_lock:
            if _ocr_instance is None:
                _ocr_instance = create_paddle_ocr()
    return _ocr_instance


def _correct_doc_orientation(image: np.ndarray) -> Tuple[np.ndarray, bool]:
    """Correct full-document orientation for form-like pages."""
    try:
        model = get_doc_orientation_model()
        result = model.predict(image)[0]
        angle = int(result.json["res"]["label_names"][0])
        if angle == 90:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE), False
        if angle == 180:
            return cv2.rotate(image, cv2.ROTATE_180), False
        if angle == 270:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE), False
    except Exception as e:
        log.warning(f"doc_orientation correction failed: {e}")
        return image, True
    return image, False


def _run_ocr_on_region(image: np.ndarray, ocr, crop_box=None):
    """Run OCR on full image or cropped region and return full-image coordinates."""
    if crop_box is not None:
        x1, y1, x2, y2 = [int(c) for c in crop_box]
        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return [], [], [], False
        ocr_region = image[y1:y2, x1:x2]
    else:
        ocr_region = image
        x1, y1 = 0, 0

    ocr_image, scale_to_original = resize_image_for_ocr(ocr_region)

    try:
        ocr_results = ocr.ocr(ocr_image)
        if ocr_results and ocr_results[0]:
            adapted = adapt_paddle_result(ocr_results)
            adapted = scale_adapted_ocr_results(adapted, scale_to_original)
        else:
            adapted = []
    except Exception as e:
        log.error(f"OCR processing error: {e}")
        return [], [], [], True

    texts, boxes, confidences = get_texts_and_boxes(adapted)

    if crop_box is not None and boxes:
        boxes = [[(pt[0] + x1, pt[1] + y1) for pt in box] for box in boxes]

    return texts, boxes, confidences, False


def _verify_skip_pan(
    all_texts: list,
    *,
    skip_keywords_enabled: bool,
    aadhaar_confirmed: bool,
) -> Dict[str, Any]:
    """Run skip-keywords and PAN checks before masking."""
    combined_text = " ".join(all_texts).lower() if all_texts else ""

    # Do not apply generic skip-keyword logic to confirmed Aadhaar card text.
    # This avoids false skip on valid card lane documents.
    if skip_keywords_enabled and combined_text and not aadhaar_confirmed:
        matched_kw = next((kw for kw in SKIP_KEYWORDS if kw in combined_text), None)
        if matched_kw:
            return {
                "skipped": True,
                "skip_reason": "skip_keywords",
                "skip_keyword": matched_kw,
                "pan_found": False,
            }

    pan_found = bool(all_texts) and (not aadhaar_confirmed) and is_pan_card(all_texts)
    if pan_found:
        return {
            "skipped": True,
            "skip_reason": "pan_card",
            "skip_keyword": None,
            "pan_found": True,
        }

    return {
        "skipped": False,
        "skip_reason": None,
        "skip_keyword": None,
        "pan_found": False,
    }


def _report_mask_counts(report: Dict[str, Any]) -> Dict[str, int]:
    return {
        "is_aadhaar": int(report.get("is_aadhaar", 0)),
        "is_number": int(report.get("is_number", 0)),
        "is_number_masked": int(report.get("is_number_masked", 0)),
        "is_qr": int(report.get("is_qr", 0)),
        "is_qr_masked": int(report.get("is_qr_masked", 0)),
        "is_xx": int(report.get("is_xx", 0)),
        "ocr_patterns_found": int(report.get("ocr_patterns_found", 0)),
    }


def _empty_yolo_report() -> Dict[str, int]:
    return {
        "is_aadhaar": 0,
        "is_number": 0,
        "is_number_masked": 0,
        "is_qr": 0,
        "is_qr_masked": 0,
        "is_xx": 0,
    }


def _derive_yolo_report_from_dets(merged_dets: list) -> Dict[str, int]:
    report = _empty_yolo_report()
    for det in merged_dets or []:
        label = str(det.get("label", "")).lower()
        if "aadhaar" in label:
            report["is_aadhaar"] += 1
        elif "number" in label:
            report["is_number"] += 1
        elif "qr" in label:
            report["is_qr"] += 1
        elif "xx" in label:
            report["is_xx"] += 1
    return report


def _run_ocr_for_card_path(image: np.ndarray, ocr, gate_result: Dict[str, Any]) -> Tuple[np.ndarray, list, list, list, bool, bool, list]:
    """OCR for card lane: crop OCR on Aadhaar cards, else fallback to full-image OCR."""
    all_texts, all_boxes, all_confidences = [], [], []
    ocr_failed = False
    doc_orientation_failed = False

    aadhaar_crops = gate_result.get("aadhaar_crops", [])
    if aadhaar_crops:
        for crop_info in aadhaar_crops:
            texts, boxes, confs, failed = _run_ocr_on_region(image, ocr, crop_box=crop_info.get("crop_box"))
            if failed:
                ocr_failed = True
            all_texts.extend(texts)
            all_boxes.extend(boxes)
            all_confidences.extend(confs)
    else:
        image, doc_orientation_failed = _correct_doc_orientation(image)
        all_texts, all_boxes, all_confidences, ocr_failed = _run_ocr_on_region(image, ocr)

    return image, all_texts, all_boxes, all_confidences, ocr_failed, doc_orientation_failed, aadhaar_crops


def _process_form_lane(
    image: np.ndarray,
    *,
    ocr,
    skip_keywords_enabled: bool,
    debug: bool,
    stats: Dict[str, Any],
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Form lane: no YOLO sweep/masking, OCR verification first, OCR-pattern masking only."""
    t0 = time.perf_counter()
    image, doc_orientation_failed = _correct_doc_orientation(image)
    all_texts, all_boxes, all_confidences, ocr_failed = _run_ocr_on_region(image, ocr)
    stats["ocr_seconds"] = time.perf_counter() - t0

    checks = _verify_skip_pan(
        all_texts,
        skip_keywords_enabled=skip_keywords_enabled,
        aadhaar_confirmed=False,
    )

    yolo_report = _empty_yolo_report()
    if checks["skipped"]:
        report = {
            **yolo_report,
            "pvc_cards_processed": 0,
            "pvc_cards_masked": 0,
            "ocr_patterns_found": 0,
            "skipped": True,
            "skip_reason": checks["skip_reason"],
            "skip_keyword": checks["skip_keyword"],
            "is_pan": checks["pan_found"],
            "lane_chosen": "form",
            "orientation_hint_angle": None,
            "final_winning_angle": None,
            "card_detected": False,
            "aadhaar_verified": False,
            "pan_found": checks["pan_found"],
            "gate_fb_confirmed": False,
            "ocr_failed": ocr_failed,
            "doc_orientation_failed": doc_orientation_failed,
        }
        report["mask_counts"] = _report_mask_counts(report)
        return image, report

    tokens_list = [
        {"text": t, "coordinates": b, "confidence": c}
        for t, b, c in zip(all_texts, all_boxes, all_confidences)
    ]
    detected_words = find_aadhaar_patterns(tokens_list)
    image = mask_ocr_detections(image, detected_words, tokens_list)

    report = {
        **yolo_report,
        "pvc_cards_processed": 0,
        "pvc_cards_masked": 0,
        "ocr_patterns_found": len(detected_words),
        "skipped": False,
        "skip_reason": None,
        "skip_keyword": None,
        "is_pan": False,
        "lane_chosen": "form",
        "orientation_hint_angle": None,
        "final_winning_angle": None,
        "card_detected": False,
        "aadhaar_verified": False,
        "pan_found": False,
        "gate_fb_confirmed": False,
        "ocr_failed": ocr_failed,
        "doc_orientation_failed": doc_orientation_failed,
    }
    report["mask_counts"] = _report_mask_counts(report)
    return image, report


def _process_card_like_lane(
    image: np.ndarray,
    *,
    lane_name: str,
    ocr,
    skip_keywords_enabled: bool,
    debug: bool,
    stats: Dict[str, Any],
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Card/uncertain lane with full gate and verification-before-masking."""
    t0 = time.perf_counter()
    image, best_angle, gate_result = find_best_orientation(image, score_fn=run_full_gate_scoring)
    stats["orientation_seconds"] = time.perf_counter() - t0
    stats["orientation_angle"] = best_angle

    t0 = time.perf_counter()
    image, all_texts, all_boxes, all_confidences, ocr_failed, doc_orientation_failed, aadhaar_crops = _run_ocr_for_card_path(
        image, ocr, gate_result
    )
    stats["ocr_seconds"] = time.perf_counter() - t0

    aadhaar_confirmed = bool(aadhaar_crops) and is_aadhaar_card_confirmed(all_texts)
    checks = _verify_skip_pan(
        all_texts,
        skip_keywords_enabled=skip_keywords_enabled,
        aadhaar_confirmed=aadhaar_confirmed,
    )

    if checks["skipped"]:
        yolo_report = _derive_yolo_report_from_dets(gate_result.get("merged_dets", []))
        report = {
            **yolo_report,
            "pvc_cards_processed": 0,
            "pvc_cards_masked": 0,
            "ocr_patterns_found": 0,
            "skipped": True,
            "skip_reason": checks["skip_reason"],
            "skip_keyword": checks["skip_keyword"],
            "is_pan": checks["pan_found"],
            "lane_chosen": lane_name,
            "orientation_hint_angle": None,
            "final_winning_angle": best_angle,
            "card_detected": bool(aadhaar_crops),
            "aadhaar_verified": bool(aadhaar_confirmed),
            "pan_found": checks["pan_found"],
            "gate_fb_confirmed": gate_result.get("fb_confirmed", False),
            "ocr_failed": ocr_failed,
            "doc_orientation_failed": doc_orientation_failed,
        }
        report["mask_counts"] = _report_mask_counts(report)
        return image, report

    pvc_stats = {"pvc_cards_processed": 0, "pvc_cards_masked": 0}
    if aadhaar_crops:
        image, pvc_stats = mask_pvc_aadhaar(image, aadhaar_crops)

    image, yolo_report = mask_yolo_detections(
        image,
        gate_result.get("merged_dets", []),
        debug=debug,
        stats=stats,
        ocr=ocr,
        aadhaar_boxes=gate_result.get("aadhaar_boxes"),
    )

    tokens_list = [
        {"text": t, "coordinates": b, "confidence": c}
        for t, b, c in zip(all_texts, all_boxes, all_confidences)
    ]
    detected_words = find_aadhaar_patterns(tokens_list)
    image = mask_ocr_detections(image, detected_words, tokens_list)

    report = {
        **yolo_report,
        **pvc_stats,
        "ocr_patterns_found": len(detected_words),
        "skipped": False,
        "skip_reason": None,
        "skip_keyword": None,
        "is_pan": False,
        "lane_chosen": lane_name,
        "orientation_hint_angle": None,
        "final_winning_angle": best_angle,
        "card_detected": bool(aadhaar_crops),
        "aadhaar_verified": bool(aadhaar_confirmed),
        "pan_found": False,
        "gate_fb_confirmed": gate_result.get("fb_confirmed", False),
        "ocr_failed": ocr_failed,
        "doc_orientation_failed": doc_orientation_failed,
    }
    report["mask_counts"] = _report_mask_counts(report)
    return image, report


def process_image(
    image: np.ndarray,
    *,
    skip_keywords_enabled: bool = True,
    debug: bool = False,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Single entry point for masking-engine and batch-processor."""
    if image is None or image.size == 0:
        raise ValueError("Input image is None or empty")

    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    stats: Dict[str, Any] = {}
    start_time = time.perf_counter()

    try:
        ocr = _get_ocr()

        router_result: Dict[str, Any] = {
            "lane": "uncertain",
            "confidence": 0.0,
            "reasoning": "router_disabled",
        }
        if ROUTER_ENABLED:
            t0 = time.perf_counter()
            ocr_tokens = run_ocr_lite_for_routing(image)
            router_result = classify_document_lane(
                ocr_tokens,
                confidence_threshold=ROUTER_CONFIDENCE_THRESHOLD,
                debug=debug,
            )
            stats["router_seconds"] = time.perf_counter() - t0
            stats["router_confidence"] = router_result.get("confidence", 0.0)

        lane = router_result.get("lane", "uncertain")
        stats["lane_chosen"] = lane

        if lane == "form":
            image, report = _process_form_lane(
                image,
                ocr=ocr,
                skip_keywords_enabled=skip_keywords_enabled,
                debug=debug,
                stats=stats,
            )
        elif lane == "card":
            image, report = _process_card_like_lane(
                image,
                lane_name="card",
                ocr=ocr,
                skip_keywords_enabled=skip_keywords_enabled,
                debug=debug,
                stats=stats,
            )
        else:
            image, report = _process_card_like_lane(
                image,
                lane_name="uncertain",
                ocr=ocr,
                skip_keywords_enabled=skip_keywords_enabled,
                debug=debug,
                stats=stats,
            )

        stats["total_seconds"] = time.perf_counter() - start_time
        report["router"] = router_result
        report["stats"] = stats
        report["mask_counts"] = _report_mask_counts(report)
        return image, report

    finally:
        gc.collect()
