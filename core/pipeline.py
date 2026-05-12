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
from core.utils.angle_detector import find_best_orientation, rotate_back_to_original_space

log = logging.getLogger(__name__)

_ocr_instance = None
_ocr_lock = threading.Lock()


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        with _ocr_lock:
            if _ocr_instance is None:
                log.info("PaddleOCR: creating singleton instance")
                _ocr_instance = create_paddle_ocr()
                log.info("PaddleOCR: singleton ready")
    return _ocr_instance


def _correct_doc_orientation(image: np.ndarray) -> Tuple[np.ndarray, bool]:
    """Correct full-document orientation for form-like pages."""
    try:
        model = get_doc_orientation_model()
        result = model.predict(image)[0]
        angle = int(result.json["res"]["label_names"][0])
        # NOTE: Log model-predicted orientation angle to make correction decisions explicit.
        log.info(f"doc_orientation: predicted_angle={angle}°")
        if angle == 90:
            log.info("doc_orientation: applied ROTATE_90_COUNTERCLOCKWISE")
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE), False
        if angle == 180:
            log.info("doc_orientation: applied ROTATE_180")
            return cv2.rotate(image, cv2.ROTATE_180), False
        if angle == 270:
            log.info("doc_orientation: applied ROTATE_90_CLOCKWISE")
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE), False
    except Exception as e:
        log.warning(f"doc_orientation correction failed: {e}")
        return image, True
    log.info("doc_orientation: no rotation needed (0°)")
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
    gate_fb_confirmed: bool = False,
) -> Dict[str, Any]:
    """Run skip-keywords and PAN checks before masking."""
    combined_text = " ".join(all_texts).lower() if all_texts else ""

    # Treat YOLO fb_confirmed as Aadhaar confirmation alongside OCR-based check.
    # Real Aadhaar cards sometimes fail OCR verification (low contrast, rotation,
    # noisy text) yet the gate has already detected the card via main+best+fb models.
    # Without this, skip_keywords or PAN noise can silently zero out masking.
    confirmed = bool(aadhaar_confirmed) or bool(gate_fb_confirmed)

    # Do not apply generic skip-keyword logic to confirmed Aadhaar card text.
    # This avoids false skip on valid card lane documents.
    if skip_keywords_enabled and combined_text and not confirmed:
        matched_kw = next((kw for kw in SKIP_KEYWORDS if kw in combined_text), None)
        if matched_kw:
            return {
                "skipped": True,
                "skip_reason": "skip_keywords",
                "skip_keyword": matched_kw,
                "pan_found": False,
            }

    pan_found = bool(all_texts) and (not confirmed) and is_pan_card(all_texts)
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


def _summarize_detection_labels(dets: list) -> Dict[str, int]:
    """Summarize merged detection labels before masking for observability."""
    counts: Dict[str, int] = {}
    for det in dets or []:
        label = str(det.get("label", "")).lower()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


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
        log.info(f"form lane: SKIPPED reason={checks['skip_reason']}")
        return image, report

    tokens_list = [
        {"text": t, "coordinates": b, "confidence": c}
        for t, b, c in zip(all_texts, all_boxes, all_confidences)
    ]
    # Form lane: enable OCR-only handwritten/noise recovery patterns for Bug 1.
    detected_words = find_aadhaar_patterns(tokens_list, form_lane_only=True)
    image = mask_ocr_detections(image, detected_words, tokens_list)
    # NOTE: No fallback OCR pass here — form lane already ran OCR on the full image above.
    # A second pass would be identical and wasteful. Card lane handles its own fallback separately.

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
    log.info(f"form lane: done ocr_patterns={len(detected_words)} ocr_failed={ocr_failed}")
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
    # NOTE: Keep original shape so we can restore output orientation for all winner angles.
    original_shape = image.shape[:2]
    t0 = time.perf_counter()
    image, best_angle, gate_result = find_best_orientation(image, score_fn=run_full_gate_scoring)
    stats["orientation_seconds"] = time.perf_counter() - t0
    stats["orientation_angle"] = best_angle
    log.info(f"{lane_name} lane: orientation={best_angle}° fb_confirmed={gate_result.get('fb_confirmed')} crops={len(gate_result.get('aadhaar_crops', []))}")

    t0 = time.perf_counter()
    image, all_texts, all_boxes, all_confidences, ocr_failed, doc_orientation_failed, aadhaar_crops = _run_ocr_for_card_path(
        image, ocr, gate_result
    )
    stats["ocr_seconds"] = time.perf_counter() - t0

    aadhaar_confirmed = bool(aadhaar_crops) and is_aadhaar_card_confirmed(all_texts)
    # NOTE: Explicit verification outcome log for Aadhaar card confirmation.
    log.info(
        f"{lane_name} lane: aadhaar_verification="
        f"{'confirmed' if aadhaar_confirmed else 'rejected'} "
        f"(crops={len(aadhaar_crops)} tokens={len(all_texts)})"
    )
    checks = _verify_skip_pan(
        all_texts,
        skip_keywords_enabled=skip_keywords_enabled,
        aadhaar_confirmed=aadhaar_confirmed,
        gate_fb_confirmed=bool(gate_result.get("fb_confirmed", False)),
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
        log.info(f"{lane_name} lane: SKIPPED reason={checks['skip_reason']}")
        
        # CRITICAL: Rotate back to original orientation even on skip.
        # Otherwise tilted documents remain tilted in output.
        if best_angle != 0:
            image = rotate_back_to_original_space(image, int(best_angle), original_shape)
            log.info(f"{lane_name} lane: rotated back to original orientation on skip (inverse of {best_angle}°)")
        
        return image, report

    pvc_stats = {"pvc_cards_processed": 0, "pvc_cards_masked": 0}
    if aadhaar_crops:
        image, pvc_stats = mask_pvc_aadhaar(image, aadhaar_crops)

    # NOTE: Log detection counts by label before masking begins.
    det_label_counts = _summarize_detection_labels(gate_result.get("merged_dets", []))
    log.info(f"{lane_name} lane: pre-mask detection counts={det_label_counts}")

    # NOTE: PAN-safe QR masking gate.
    # - If Aadhaar OCR is confirmed, allow QR masking with Aadhaar boxes.
    # - If OCR confirmation is weak but detector found primary Aadhaar-number labels,
    #   still allow QR masking (prevents no-mask regression on real Aadhaar cards).
    # - Helper-only labels (e.g. is_number) do not open this gate.
    merged_dets = gate_result.get("merged_dets", [])
    has_primary_number_det = any(
        str(d.get("label", "")).lower() in {"number", "number_inverse", "number_anticlockwise"}
        and float(d.get("conf", 0.0)) > 0.3
        for d in merged_dets
    )
    # NOTE: Some valid Aadhaar pages fail OCR verification but are still gate-confirmed
    # via FB+YOLO. In those cases, keep QR masking enabled with Aadhaar-box spatial checks.
    gate_fb_confirmed = bool(gate_result.get("fb_confirmed", False))
    qr_masking_allowed = bool(aadhaar_confirmed) or has_primary_number_det or gate_fb_confirmed

    image, yolo_report = mask_yolo_detections(
        image,
        merged_dets,
        debug=debug,
        stats=stats,
        ocr=ocr,
        aadhaar_boxes=(gate_result.get("aadhaar_boxes") if qr_masking_allowed else []),
        gate_fb_confirmed=gate_fb_confirmed,
    )

    tokens_list = [
        {"text": t, "coordinates": b, "confidence": c}
        for t, b, c in zip(all_texts, all_boxes, all_confidences)
    ]
    # Card/uncertain lane: keep legacy OCR pattern behavior (no form-lane extensions).
    detected_words = find_aadhaar_patterns(tokens_list, form_lane_only=False)
    image = mask_ocr_detections(image, detected_words, tokens_list)

    # Rotate back to original orientation after all masking is complete.
    # NOTE: Supports both cardinal and non-cardinal winners (45/135/225/315).
    if best_angle != 0:
        image = rotate_back_to_original_space(image, int(best_angle), original_shape)
        log.info(f"{lane_name} lane: rotated back to original orientation (inverse of {best_angle}°)")

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
    log.info(
        f"{lane_name} lane: done angle={best_angle}° "
        f"pvc_processed={pvc_stats['pvc_cards_processed']} pvc_masked={pvc_stats['pvc_cards_masked']} "
        f"ocr_patterns={len(detected_words)} aadhaar_verified={bool(aadhaar_confirmed)}"
    )
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
    log.info(f"process_image: start shape={image.shape[1]}x{image.shape[0]}")

    try:
        ocr = _get_ocr()

        router_result: Dict[str, Any] = {
            "lane": "uncertain",
            "confidence": 0.0,
            "reasoning": "router_disabled",
        }
        if ROUTER_ENABLED:
            t0 = time.perf_counter()
            ocr_tokens = run_ocr_lite_for_routing(image, ocr=ocr)
            router_result = classify_document_lane(
                ocr_tokens,
                confidence_threshold=ROUTER_CONFIDENCE_THRESHOLD,
                debug=debug,
            )
            stats["router_seconds"] = time.perf_counter() - t0
            stats["router_confidence"] = router_result.get("confidence", 0.0)

        lane = router_result.get("lane", "uncertain")
        stats["lane_chosen"] = lane
        log.info(f"process_image: lane={lane} confidence={router_result.get('confidence', 0.0):.2f} reason={router_result.get('reasoning', '')[:60]}")

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
        log.info(
            f"process_image: done lane={report.get('lane_chosen')} "
            f"angle={report.get('final_winning_angle')} skip={report.get('skipped')} "
            f"masks={report.get('mask_counts')} t={stats['total_seconds']:.2f}s"
        )
        return image, report

    finally:
        gc.collect()
