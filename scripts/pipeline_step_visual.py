"""
pipeline_step_visual.py

Run one image through the AHFL pipeline and save visual outputs at each stage.

Usage:
  python scripts/pipeline_step_visual.py --input /path/in.png --out /path/debug_out
"""

import argparse
import json
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


def run_debug(input_path: Path, out_dir: Path):
    image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {input_path}")

    report = {
        "input": str(input_path),
        "stages": [],
    }

    _save_image(out_dir / "00_original.png", image)
    report["stages"].append({"name": "00_original", "file": "00_original.png"})

    ocr = _get_ocr()
    router_result = {
        "lane": "uncertain",
        "confidence": 0.0,
        "reasoning": "router_disabled",
    }

    if ROUTER_ENABLED:
        ocr_tokens = run_ocr_lite_for_routing(image, ocr=ocr)
        router_result = classify_document_lane(
            ocr_tokens,
            confidence_threshold=ROUTER_CONFIDENCE_THRESHOLD,
            debug=True,
        )

    lane = router_result.get("lane", "uncertain")
    report["router"] = router_result

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

            tokens_list = _tokens_from_ocr(all_texts, all_boxes, all_confidences)
            detected_words = find_aadhaar_patterns(tokens_list)
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

    with open(out_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


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
