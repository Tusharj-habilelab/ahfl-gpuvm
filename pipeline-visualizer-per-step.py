"""
pipeline_step_visual.py

Run one image through the AHFL pipeline and save visual outputs at each stage.

Usage:
  python scripts/pipeline_step_visual.py --input /path/in.png --out /path/debug_out
"""

import argparse
import json
import logging
import time
from pathlib import Path

import cv2

from core.aadhaar_gate import run_full_gate_scoring
from core.classifiers import is_aadhaar_card_confirmed, mask_pvc_aadhaar
from core.config import ROUTER_CONFIDENCE_THRESHOLD, ROUTER_ENABLED
from core.ocr.masking import find_aadhaar_patterns, mask_ocr_detections, mask_yolo_detections
from core.ocr.ocr_adapter import get_texts_and_boxes
from core.ocr.paddle import run_ocr_lite_for_routing
from core.pipeline import (
    _correct_doc_orientation,
    _get_ocr,
    _run_ocr_for_card_path,
    _run_ocr_on_region,
    _verify_skip_pan,
)
from core.router import classify_document_lane
from core.utils.angle_detector import find_best_orientation, rotate_image


def _save_image(path: Path, image):
    path.parent.mkdir(parents=True, exist_ok=True)
    # NOTE: Explicit check to fail fast if artifact write fails.
    if not cv2.imwrite(str(path), image):
        raise IOError(f"Failed to write image: {path}")


def _tokens_from_ocr(texts, boxes, confidences):
    return [
        {"text": t, "coordinates": b, "confidence": c}
        for t, b, c in zip(texts, boxes, confidences)
    ]


def _bbox_from_poly(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def _draw_boxes(image, box_items, color, title=""):
    out = image.copy()
    for item in box_items:
        x1, y1, x2, y2 = item["box"]
        label = item.get("label", "")
        cv2.rectangle(out, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        if label:
            cv2.putText(
                out,
                label,
                (int(x1), max(12, int(y1) - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )
    if title:
        cv2.putText(out, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return out


def _draw_tokens(image, tokens, color, title=""):
    out = image.copy()
    for t in tokens:
        try:
            x1, y1, x2, y2 = _bbox_from_poly(t["coordinates"])
        except Exception:
            continue
        txt = str(t.get("text", ""))[:24]
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        if txt:
            cv2.putText(
                out,
                txt,
                (x1, max(12, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                color,
                1,
                cv2.LINE_AA,
            )
    if title:
        cv2.putText(out, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return out


def _draw_detected_words(image, detected_words, color, title=""):
    out = image.copy()
    for dw in detected_words:
        coords = dw.get("coordinates", [])
        if not coords:
            continue
        try:
            x1, y1, x2, y2 = _bbox_from_poly(coords)
        except Exception:
            continue
        label = f"{dw.get('type', '')}:{str(dw.get('text', ''))[:14]}"
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        cv2.putText(out, label, (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
    if title:
        cv2.putText(out, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return out


def _attach_file_logger(log_path: Path):
    """Attach root logger handler so all module logs are captured in one artifact file."""
    root = logging.getLogger()
    # NOTE: INFO level is used so normal pipeline logs are captured without debug mode.
    root.setLevel(logging.INFO)
    handler = logging.FileHandler(str(log_path), mode="w", encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s", "%Y-%m-%d %H:%M:%S"))
    root.addHandler(handler)
    return root, handler


def _detach_file_logger(root_logger, handler):
    root_logger.removeHandler(handler)
    handler.close()


def run_debug(input_path: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / "pipeline_debug.log"
    root_logger, file_handler = _attach_file_logger(log_file)

    image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if image is None:
        _detach_file_logger(root_logger, file_handler)
        raise ValueError(f"Cannot read image: {input_path}")

    report = {
        "input": str(input_path),
        "stages": [],
        "log_file": str(log_file.name),
    }
    t_total_start = time.perf_counter()

    logging.getLogger(__name__).info(f"visualizer start: input={input_path}")

    _save_image(out_dir / "00_original.png", image)
    report["stages"].append({"name": "00_original", "file": "00_original.png"})

    ocr = _get_ocr()
    # NOTE: Initialize to empty list so report serialization is safe when router is disabled.
    ocr_tokens = []
    router_result = {
        "lane": "uncertain",
        "confidence": 0.0,
        "reasoning": "router_disabled",
    }

    if ROUTER_ENABLED:
        t_router = time.perf_counter()
        # NOTE: Defensive fallback to [] if OCR-lite returns None.
        ocr_tokens = run_ocr_lite_for_routing(image, ocr=ocr) or []
        router_result = classify_document_lane(
            ocr_tokens,
            confidence_threshold=ROUTER_CONFIDENCE_THRESHOLD,
            debug=True,
        )
        report["router_seconds"] = round(time.perf_counter() - t_router, 4)

    lane = router_result.get("lane", "uncertain")
    report["router"] = router_result

    # NOTE: Save router token evidence for classification debugging.
    with open(out_dir / "router_tokens.json", "w", encoding="utf-8") as f:
        json.dump({"tokens": ocr_tokens if ROUTER_ENABLED else []}, f, indent=2)

    if lane == "form":
        oriented, doc_orientation_failed = _correct_doc_orientation(image.copy())
        _save_image(out_dir / "10_form_oriented.png", oriented)
        report["stages"].append({
            "name": "10_form_oriented",
            "file": "10_form_oriented.png",
            "doc_orientation_failed": bool(doc_orientation_failed),
        })

        texts, boxes, confidences, ocr_failed = _run_ocr_on_region(oriented, ocr)
        tokens_list = _tokens_from_ocr(texts, boxes, confidences)
        form_tokens_img = _draw_tokens(oriented, tokens_list, (0, 220, 0), "FORM OCR TOKENS")
        _save_image(out_dir / "15_form_ocr_tokens.png", form_tokens_img)
        report["stages"].append({
            "name": "15_form_ocr_tokens",
            "file": "15_form_ocr_tokens.png",
            "token_count": len(tokens_list),
        })

        checks = _verify_skip_pan(
            texts,
            skip_keywords_enabled=True,
            aadhaar_confirmed=False,
        )
        report["form"] = {
            "ocr_failed": bool(ocr_failed),
            "tokens": len(tokens_list),
            "skip": checks,
        }

        if not checks["skipped"]:
            detected_words = find_aadhaar_patterns(tokens_list)
            patterns_overlay = _draw_detected_words(oriented, detected_words, (0, 140, 255), "FORM OCR PATTERNS")
            _save_image(out_dir / "18_form_ocr_patterns.png", patterns_overlay)
            report["stages"].append({
                "name": "18_form_ocr_patterns",
                "file": "18_form_ocr_patterns.png",
                "ocr_patterns": len(detected_words),
            })

            after_ocr = mask_ocr_detections(oriented.copy(), detected_words, tokens_list)
            _save_image(out_dir / "20_form_after_ocr_mask.png", after_ocr)
            report["stages"].append({
                "name": "20_form_after_ocr_mask",
                "file": "20_form_after_ocr_mask.png",
                "ocr_patterns": len(detected_words),
            })
            _save_image(out_dir / "99_final.png", after_ocr)
        else:
            _save_image(out_dir / "99_final.png", oriented)

    else:
        # NOTE: Card/uncertain share the full gate + orientation path.
        oriented, best_angle, gate_result = find_best_orientation(image.copy(), score_fn=run_full_gate_scoring)
        _save_image(out_dir / "10_oriented_best.png", oriented)
        report["stages"].append({
            "name": "10_oriented_best",
            "file": "10_oriented_best.png",
            "best_angle": int(best_angle),
        })

        # NOTE: Save merged detections and Aadhaar crop boxes before masking.
        merged_dets = gate_result.get("merged_dets", [])
        pre_mask_boxes = [
            {
                "box": [int(d["box"][0]), int(d["box"][1]), int(d["box"][2]), int(d["box"][3])],
                "label": f"{d.get('label', '')}:{float(d.get('conf', 0.0)):.2f}",
            }
            for d in merged_dets
        ]
        stage_gate = _draw_boxes(oriented, pre_mask_boxes, (160, 0, 200), "GATE MERGED DETECTIONS")
        _save_image(out_dir / "12_gate_merged_detections.png", stage_gate)
        report["stages"].append({
            "name": "12_gate_merged_detections",
            "file": "12_gate_merged_detections.png",
            "detections": len(pre_mask_boxes),
        })

        aadhaar_box_items = []
        for idx, box in enumerate(gate_result.get("aadhaar_boxes", []) or []):
            aadhaar_box_items.append(
                {
                    "box": [int(box[0]), int(box[1]), int(box[2]), int(box[3])],
                    "label": f"aadhaar_box_{idx+1}",
                }
            )
        stage_aadhaar_boxes = _draw_boxes(oriented, aadhaar_box_items, (0, 255, 255), "AADHAAR CARD BOXES")
        _save_image(out_dir / "13_gate_aadhaar_boxes.png", stage_aadhaar_boxes)
        report["stages"].append({
            "name": "13_gate_aadhaar_boxes",
            "file": "13_gate_aadhaar_boxes.png",
            "aadhaar_boxes": len(aadhaar_box_items),
        })

        work_img, all_texts, all_boxes, all_confidences, ocr_failed, doc_orientation_failed, aadhaar_crops = _run_ocr_for_card_path(
            oriented.copy(), ocr, gate_result
        )
        _save_image(out_dir / "20_after_card_ocr_prep.png", work_img)
        report["stages"].append({
            "name": "20_after_card_ocr_prep",
            "file": "20_after_card_ocr_prep.png",
            "ocr_failed": bool(ocr_failed),
            "doc_orientation_failed": bool(doc_orientation_failed),
            "aadhaar_crops": len(aadhaar_crops),
        })

        tokens_list = _tokens_from_ocr(all_texts, all_boxes, all_confidences)
        all_tokens_overlay = _draw_tokens(work_img, tokens_list, (0, 220, 0), "CARD OCR TOKENS")
        _save_image(out_dir / "21_card_ocr_tokens.png", all_tokens_overlay)
        report["stages"].append({
            "name": "21_card_ocr_tokens",
            "file": "21_card_ocr_tokens.png",
            "token_count": len(tokens_list),
        })

        aadhaar_kw_tokens = [
            t for t in tokens_list
            if "aadhaar" in str(t.get("text", "")).lower() or "aadhar" in str(t.get("text", "")).lower()
        ]
        kw_overlay = _draw_tokens(work_img, aadhaar_kw_tokens, (0, 255, 255), "CARD OCR AADHAAR KEYWORDS")
        _save_image(out_dir / "22_card_ocr_aadhaar_keywords.png", kw_overlay)
        report["stages"].append({
            "name": "22_card_ocr_aadhaar_keywords",
            "file": "22_card_ocr_aadhaar_keywords.png",
            "aadhaar_keyword_tokens": len(aadhaar_kw_tokens),
        })

        aadhaar_confirmed = bool(aadhaar_crops) and is_aadhaar_card_confirmed(all_texts)
        checks = _verify_skip_pan(
            all_texts,
            skip_keywords_enabled=True,
            aadhaar_confirmed=aadhaar_confirmed,
        )
        report["card"] = {
            "aadhaar_confirmed": bool(aadhaar_confirmed),
            "skip": checks,
        }

        if checks["skipped"]:
            _save_image(out_dir / "99_final.png", work_img)
        else:
            after_pvc = work_img.copy()
            if aadhaar_crops:
                after_pvc, pvc_stats = mask_pvc_aadhaar(after_pvc, aadhaar_crops)
            else:
                pvc_stats = {"pvc_cards_processed": 0, "pvc_cards_masked": 0}
            _save_image(out_dir / "30_after_pvc_mask.png", after_pvc)
            report["stages"].append({
                "name": "30_after_pvc_mask",
                "file": "30_after_pvc_mask.png",
                **pvc_stats,
            })

            after_yolo, yolo_report = mask_yolo_detections(
                after_pvc.copy(),
                gate_result.get("merged_dets", []),
                debug=True,
                stats={},
                ocr=ocr,
                aadhaar_boxes=gate_result.get("aadhaar_boxes"),
            )
            _save_image(out_dir / "40_after_yolo_mask.png", after_yolo)
            report["stages"].append({
                "name": "40_after_yolo_mask",
                "file": "40_after_yolo_mask.png",
                "yolo_report": yolo_report,
            })

            detected_words = find_aadhaar_patterns(tokens_list)
            pattern_overlay = _draw_detected_words(after_yolo, detected_words, (0, 140, 255), "CARD OCR PATTERNS")
            _save_image(out_dir / "45_card_ocr_patterns_overlay.png", pattern_overlay)
            report["stages"].append({
                "name": "45_card_ocr_patterns_overlay",
                "file": "45_card_ocr_patterns_overlay.png",
                "ocr_patterns": len(detected_words),
            })

            after_ocr = mask_ocr_detections(after_yolo.copy(), detected_words, tokens_list)
            _save_image(out_dir / "50_after_ocr_mask.png", after_ocr)
            report["stages"].append({
                "name": "50_after_ocr_mask",
                "file": "50_after_ocr_mask.png",
                "ocr_patterns": len(detected_words),
            })

            final_img = after_ocr
            if best_angle != 0:
                inverse_angle = {90: 270, 180: 180, 270: 90}.get(best_angle, 0)
                if inverse_angle != 0:
                    final_img = rotate_image(final_img, inverse_angle)
            _save_image(out_dir / "99_final.png", final_img)

    report["total_seconds"] = round(time.perf_counter() - t_total_start, 4)

    with open(out_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logging.getLogger(__name__).info(f"visualizer complete: out_dir={out_dir} total_seconds={report['total_seconds']}")
    _detach_file_logger(root_logger, file_handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--out", required=True, help="Output directory for stage images")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out)
    run_debug(input_path, out_dir)
    print(f"Saved stage artifacts to: {out_dir}")


if __name__ == "__main__":
    main()
