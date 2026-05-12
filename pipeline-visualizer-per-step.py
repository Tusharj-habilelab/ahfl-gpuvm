"""
pipeline_step_visual.py

Run one image through the AHFL pipeline and emit forensic artifacts in an exact tree.

Usage:
    python pipeline-visualizer-per-step.py --input /path/in.png --out /path/output_root
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch

from core.classifiers import detect_aadhaar_side, is_aadhaar_card_confirmed, mask_pvc_aadhaar
from core.config import GPU_ENABLED, ROUTER_CONFIDENCE_THRESHOLD, ROUTER_ENABLED, YOLO_MAIN_DILATE_ENABLED
from core.models.yolo_runner import get_yolo_best, get_yolo_main
from core.ocr.masking import (
        find_aadhaar_patterns,
        mask_ocr_detections,
        mask_yolo_detections,
        merge_detections,
        yolo_results_to_detections,
)
from core.ocr.paddle import run_ocr_lite_for_routing
from core.pipeline import (
        _correct_doc_orientation,
        _get_ocr,
        _run_ocr_for_card_path,
        _run_ocr_on_region,
        _verify_skip_pan,
)
from core.router import classify_document_lane
from core.spatial import filter_dets_inside_box, map_crop_dets_to_full
from core.utils.angle_detector import rotate_back_to_original_space, rotate_image, rotate_image_affine


_USE_HALF = bool(GPU_ENABLED and torch.cuda.is_available())
_FORENSIC_ANGLES = [0, 45, 90, 135, 180, 225, 270, 315]


def _save_image(path: Path, image):
    path.parent.mkdir(parents=True, exist_ok=True)
    # NOTE: Explicit check to fail fast if artifact write fails.
    if not cv2.imwrite(str(path), image):
        raise IOError(f"Failed to write image: {path}")


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _na_marker(path: Path, reason: str, extra: Optional[Dict[str, Any]] = None) -> None:
    marker = {"not_applicable": True, "reason": reason}
    if extra:
        marker.update(extra)
    _save_json(path, marker)


def _tokens_from_ocr(texts, boxes, confidences):
    return [
        {"text": t, "coordinates": b, "confidence": c}
        for t, b, c in zip(texts, boxes, confidences)
    ]


def _bbox_from_poly(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def _box_area(box: List[float]) -> float:
    return max(0.0, float(box[2] - box[0])) * max(0.0, float(box[3] - box[1]))


def _rect_intersection(a: List[float], b: List[float]) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return float(x2 - x1) * float(y2 - y1)


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


def _draw_token_polygons(image, tokens, color, title=""):
    out = image.copy()
    for t in tokens:
        coords = t.get("coordinates")
        if not coords:
            continue
        try:
            pts = np.array([[int(p[0]), int(p[1])] for p in coords], dtype=np.int32)
            if pts.shape[0] >= 3:
                cv2.polylines(out, [pts], isClosed=True, color=color, thickness=2)
        except Exception:
            continue
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


def _draw_poly_regions(image, polygons: List[List[Tuple[float, float]]], color, title=""):
    out = image.copy()
    for poly in polygons:
        try:
            pts = np.array([[int(p[0]), int(p[1])] for p in poly], dtype=np.int32)
            if pts.shape[0] >= 3:
                cv2.polylines(out, [pts], isClosed=True, color=color, thickness=2)
        except Exception:
            continue
    if title:
        cv2.putText(out, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return out


def _count_labels(dets: List[dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for det in dets or []:
        label = str(det.get("label", "")).lower()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


def _derive_yolo_report_from_dets(merged_dets: List[dict]) -> Dict[str, int]:
    """
    Mirror core.pipeline skip-branch aggregation:
    when masking is skipped, still report detected label counts.
    """
    report = {
        "is_aadhaar": 0,
        "is_number": 0,
        "is_number_masked": 0,
        "is_qr": 0,
        "is_qr_masked": 0,
        "is_xx": 0,
    }
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


def _rot(image: np.ndarray, angle: int) -> np.ndarray:
    if angle in (0, 90, 180, 270):
        return rotate_image(image, angle)
    return rotate_image_affine(image, float(angle))


def _preprocess_grey(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if YOLO_MAIN_DILATE_ENABLED:
        kernel = np.ones((2, 2), np.uint8)
        pre = cv2.dilate(grey, kernel, iterations=1)
    else:
        pre = grey
    return grey, pre


def _run_gate_once(rotated: np.ndarray) -> Dict[str, Any]:
    grey, pre = _preprocess_grey(rotated)
    pre_bgr = cv2.cvtColor(pre, cv2.COLOR_GRAY2BGR)

    yolo_main = get_yolo_main()
    yolo_best = get_yolo_best()

    main_results = yolo_main(pre_bgr, half=_USE_HALF)[0]
    main_dets = yolo_results_to_detections(main_results, model_name="main")
    del main_results
    del pre_bgr

    coordinates = [d["box"] for d in main_dets]
    labels = [d["label"] for d in main_dets]
    confs = [d["conf"] for d in main_dets]
    side_result = detect_aadhaar_side(
        grey,
        coordinates,
        labels,
        confs,
        return_metadata=True,
    )
    if len(side_result) == 4:
        f_coords, f_labels, f_confs, f_meta = side_result
    else:
        f_coords, f_labels, f_confs = side_result
        f_meta = [{} for _ in f_coords]
    fb_filtered = [
        {"box": c, "label": l, "conf": cf, "model": "main+fb", **m}
        for c, l, cf, m in zip(f_coords, f_labels, f_confs, f_meta)
    ]

    aadhaar_dets = [d for d in fb_filtered if str(d.get("label", "")).lower() == "aadhaar"]
    aadhaar_boxes = [d["box"] for d in aadhaar_dets]

    best_full: List[dict] = []
    merged_all: List[dict] = []
    crop_details: List[dict] = []

    if aadhaar_dets:
        for idx, ad in enumerate(aadhaar_dets, start=1):
            x1, y1, x2, y2 = [int(v) for v in ad["box"]]
            h, w = rotated.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            crop_box = [x1, y1, x2, y2]
            crop_img = rotated[y1:y2, x1:x2]
            best_results = yolo_best(crop_img, half=_USE_HALF)[0]
            best_crop = yolo_results_to_detections(best_results, model_name="best")
            del best_results

            best_mapped = map_crop_dets_to_full(best_crop, [float(v) for v in crop_box])
            main_inside = filter_dets_inside_box(fb_filtered, [float(v) for v in crop_box])
            merged_inside = merge_detections(main_inside, best_mapped)

            best_full.extend(best_mapped)
            merged_all.extend(merged_inside)
            crop_details.append(
                {
                    "crop_index": idx,
                    "crop_box": crop_box,
                    "main_inside": main_inside,
                    "best_inside": best_mapped,
                    "merged_inside": merged_inside,
                    "fb_classes": ad.get("fb_classes", []),
                }
            )

        crop_boxes = [c["crop_box"] for c in crop_details]
        for det in fb_filtered:
            if str(det.get("label", "")).lower() == "aadhaar":
                continue
            inside_any = any(len(filter_dets_inside_box([det], box)) > 0 for box in crop_boxes)
            if not inside_any:
                merged_all.append(det)
    else:
        best_results = yolo_best(rotated, half=_USE_HALF)[0]
        best_full = yolo_results_to_detections(best_results, model_name="best")
        del best_results
        merged_all = merge_detections(fb_filtered, best_full)

    aadhaar_confs = [d["conf"] for d in fb_filtered if str(d.get("label", "")).lower() == "aadhaar"]
    if aadhaar_confs:
        score = max(aadhaar_confs) + min(len(aadhaar_confs), 3) * 0.05 + 0.1
    else:
        raw_aadhaar_confs = [d["conf"] for d in main_dets if str(d.get("label", "")).lower() == "aadhaar"]
        if raw_aadhaar_confs:
            score = max(raw_aadhaar_confs) * 0.5
        else:
            score = len(main_dets) * 0.01

    best_number_confs = [d["conf"] for d in merged_all if "number" in str(d.get("label", "")).lower() and d.get("model") == "best"]
    best_qr_confs = [d["conf"] for d in merged_all if "qr" in str(d.get("label", "")).lower() and d.get("model") == "best"]

    return {
        "score": float(score),
        "rotated": rotated,
        "main_dets": main_dets,
        "fb_filtered": fb_filtered,
        "best_dets_full": best_full,
        "merged_dets": merged_all,
        "aadhaar_boxes": aadhaar_boxes,
        "aadhaar_crops": crop_details,
        "fb_confirmed": len(aadhaar_confs) > 0,
        "max_aadhaar_conf": max(aadhaar_confs) if aadhaar_confs else 0.0,
        "best_number_conf": max(best_number_confs) if best_number_confs else 0.0,
        "best_qr_conf": max(best_qr_confs) if best_qr_confs else 0.0,
    }


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


def _make_tree(base_out_dir: Path, input_path: Path) -> Dict[str, Any]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = input_path.stem.replace(" ", "_")
    run_root = base_out_dir / f"image-{stem}--{ts}"

    folders = {
        "run_root": run_root,
        "input": run_root / "000_input",
        "router": run_root / "100_router",
        "angles": run_root / "200_orientation_all_angles",
        "winner": run_root / "300_winner",
        "crops": run_root / "320_aadhaar_crops_before_ocr_prep",
        "card": run_root / "400_card_ocr_and_mask",
        "reports": run_root / "900_reports",
    }
    for p in folders.values():
        if isinstance(p, Path):
            p.mkdir(parents=True, exist_ok=True)
    return {"ts": ts, "folders": folders}


def _build_db_parity_report(
    *,
    input_path: Path,
    lane: str,
    winner_angle: int,
    skip_reason: Optional[str],
    pan_found: bool,
    card_detected: bool,
    aadhaar_verified: bool,
    yolo_report: Dict[str, int],
    ocr_patterns_found: int,
    total_seconds: float,
    orientation_scores: List[Dict[str, Any]],
) -> Dict[str, Any]:
    mask_counts = {
        "is_aadhaar": int(yolo_report.get("is_aadhaar", 0) or 0),
        "is_number": int(yolo_report.get("is_number", 0) or 0),
        "is_number_masked": int(yolo_report.get("is_number_masked", 0) or 0),
        "is_qr": int(yolo_report.get("is_qr", 0) or 0),
        "is_qr_masked": int(yolo_report.get("is_qr_masked", 0) or 0),
        "is_xx": int(yolo_report.get("is_xx", 0) or 0),
        "ocr_patterns_found": int(ocr_patterns_found),
    }
    mask_counts["is_aadhaar"] = int(mask_counts["is_aadhaar"] or any(mask_counts[k] > 0 for k in ["is_number", "is_number_masked", "is_qr", "is_qr_masked", "is_xx", "ocr_patterns_found"]))

    return {
        "report_schema_version": "2.0",
        "input": str(input_path),
        "lane_chosen": lane,
        "final_winning_angle": int(winner_angle),
        "skip_reason": skip_reason,
        "card_detected": bool(card_detected),
        "aadhaar_verified": bool(aadhaar_verified),
        "pan_found": bool(pan_found),
        "mask_counts": mask_counts,
        # NOTE: Flat compatibility fields retained by request.
        "is_aadhaar": int(mask_counts["is_aadhaar"]),
        "is_number": int(mask_counts["is_number"]),
        "is_number_masked": int(mask_counts["is_number_masked"]),
        "is_QR": int(mask_counts["is_qr"]),
        "is_QR_masked": int(mask_counts["is_qr_masked"]),
        "is_XX": int(mask_counts["is_xx"]),
        "ocr_patterns_found": int(mask_counts["ocr_patterns_found"]),
        "orientation_scores": orientation_scores,
        "total_seconds": float(round(total_seconds, 4)),
    }


def run_debug(input_path: Path, out_dir: Path):
    layout = _make_tree(out_dir, input_path)
    folders = layout["folders"]

    # NOTE: Log file moved to strict reports location.
    log_file = folders["reports"] / "990_pipeline_debug.log"
    root_logger, file_handler = _attach_file_logger(log_file)

    image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if image is None:
        _detach_file_logger(root_logger, file_handler)
        raise ValueError(f"Cannot read image: {input_path}")
    original_shape = image.shape[:2]

    report_stages = []
    t_total_start = time.perf_counter()

    logging.getLogger(__name__).info(f"visualizer start: input={input_path}")

    _save_image(folders["input"] / "000_original.png", image)
    _save_json(
        folders["input"] / "001_input_meta.json",
        {
            "input": str(input_path),
            "shape": [int(v) for v in image.shape],
            "dtype": str(image.dtype),
            "run_id": layout["ts"],
        },
    )

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
        router_seconds = round(time.perf_counter() - t_router, 4)
    else:
        router_seconds = 0.0

    lane = router_result.get("lane", "uncertain")
    _save_json(folders["router"] / "100_ocr_lite_tokens.json", {"tokens": ocr_tokens if ROUTER_ENABLED else []})
    _save_json(
        folders["router"] / "110_router_decision.json",
        {"router": router_result, "router_seconds": router_seconds},
    )

    orientation_scores: List[Dict[str, Any]] = []
    model_findings: Dict[str, Any] = {"angles": []}
    winner_angle = 0
    winner_data: Dict[str, Any] = {}

    if lane in ("card", "uncertain"):
        # NOTE: Full-angle forensic sweep for exact tree contract.
        for angle in _FORENSIC_ANGLES:
            rotated = _rot(image.copy(), angle)
            gate_data = _run_gate_once(rotated)

            angle_tag = f"{angle:03d}"
            angle_dir = folders["angles"] / f"angle_{angle_tag}"
            angle_dir.mkdir(parents=True, exist_ok=True)

            _save_image(angle_dir / f"201_{angle_tag}_rotated.png", gate_data["rotated"])

            main_overlay = _draw_boxes(
                gate_data["rotated"],
                [
                    {
                        "box": [int(d["box"][0]), int(d["box"][1]), int(d["box"][2]), int(d["box"][3])],
                        "label": f"{d.get('label', '')}:{float(d.get('conf', 0.0)):.2f}",
                    }
                    for d in gate_data["main_dets"]
                ],
                (255, 120, 0),
                "MAIN DETECTIONS",
            )
            _save_image(angle_dir / f"211_{angle_tag}_main_detections.png", main_overlay)

            fb_overlay = _draw_boxes(
                gate_data["rotated"],
                [
                    {
                        "box": [int(d["box"][0]), int(d["box"][1]), int(d["box"][2]), int(d["box"][3])],
                        "label": f"{d.get('label', '')}:{float(d.get('conf', 0.0)):.2f}",
                    }
                    for d in gate_data["fb_filtered"]
                ],
                (0, 220, 255),
                "FB FILTERED",
            )
            _save_image(angle_dir / f"212_{angle_tag}_fb_filtered.png", fb_overlay)

            best_overlay = _draw_boxes(
                gate_data["rotated"],
                [
                    {
                        "box": [int(d["box"][0]), int(d["box"][1]), int(d["box"][2]), int(d["box"][3])],
                        "label": f"{d.get('label', '')}:{float(d.get('conf', 0.0)):.2f}",
                    }
                    for d in gate_data["best_dets_full"]
                ],
                (0, 255, 120),
                "BEST DETECTIONS",
            )
            _save_image(angle_dir / f"213_{angle_tag}_best_detections.png", best_overlay)

            merged_overlay = _draw_boxes(
                gate_data["rotated"],
                [
                    {
                        "box": [int(d["box"][0]), int(d["box"][1]), int(d["box"][2]), int(d["box"][3])],
                        "label": f"{d.get('label', '')}:{float(d.get('conf', 0.0)):.2f}",
                    }
                    for d in gate_data["merged_dets"]
                ],
                (180, 0, 220),
                "MERGED DETECTIONS",
            )
            _save_image(angle_dir / f"214_{angle_tag}_merged_detections.png", merged_overlay)

            findings = {
                "angle": int(angle),
                "score": float(gate_data["score"]),
                "max_aadhaar_conf": float(gate_data["max_aadhaar_conf"]),
                "best_number_conf": float(gate_data["best_number_conf"]),
                "best_qr_conf": float(gate_data["best_qr_conf"]),
                "fb_confirmed": bool(gate_data["fb_confirmed"]),
                "counts": {
                    "main": _count_labels(gate_data["main_dets"]),
                    "fb_filtered": _count_labels(gate_data["fb_filtered"]),
                    "best": _count_labels(gate_data["best_dets_full"]),
                    "merged": _count_labels(gate_data["merged_dets"]),
                },
                "aadhaar_boxes": gate_data["aadhaar_boxes"],
            }
            _save_json(angle_dir / f"215_{angle_tag}_findings.json", findings)

            orientation_scores.append({"angle": int(angle), "score": float(gate_data["score"])})
            model_findings["angles"].append(findings)

            if not winner_data or gate_data["score"] > winner_data["score"]:
                winner_data = gate_data
                winner_angle = angle

        _save_json(
            folders["angles"] / "200_angles_summary.json",
            {
                "angles": orientation_scores,
                "winner_angle": int(winner_angle),
                "winner_score": float(winner_data.get("score", 0.0)),
            },
        )
    else:
        # NOTE: Form lane still gets the full tree; angle folders are marked not applicable.
        _save_json(folders["angles"] / "200_angles_summary.json", {
            "not_applicable_reason": "form_lane_does_not_run_orientation_sweep",
            "angles": [],
        })
        _na_marker(
            folders["angles"] / "angle_000" / "215_000_findings_not_applicable.json",
            "form_lane_does_not_run_orientation_sweep",
        )

    if lane == "form":
        oriented, doc_orientation_failed = _correct_doc_orientation(image.copy())
        _save_image(folders["winner"] / "310_oriented_best.png", oriented)
        _na_marker(folders["winner"] / "300_best_angle_not_applicable.json", "form_lane_has_no_angle_winner")
        _na_marker(folders["winner"] / "312_gate_merged_detections_not_applicable.json", "form_lane_has_no_gate_merge")
        _na_marker(folders["winner"] / "313_gate_aadhaar_boxes_not_applicable.json", "form_lane_has_no_gate_boxes")
        _save_json(
            folders["winner"] / "folder_not_applicable_reason.json",
            {"not_applicable_reason": "form_lane_uses_ocr_first_flow"},
        )

        texts, boxes, confidences, ocr_failed = _run_ocr_on_region(oriented, ocr)
        tokens_list = _tokens_from_ocr(texts, boxes, confidences)
        form_tokens_axis = _draw_tokens(oriented, tokens_list, (0, 220, 0), "FORM OCR TOKENS AXIS")
        form_tokens_poly = _draw_token_polygons(oriented, tokens_list, (220, 200, 0), "FORM OCR TOKENS POLYGON")
        _save_image(folders["card"] / "410_card_ocr_tokens_axis.png", form_tokens_axis)
        _save_image(folders["card"] / "411_card_ocr_tokens_polygon.png", form_tokens_poly)
        _save_image(folders["card"] / "400_after_card_ocr_prep.png", oriented)

        checks = _verify_skip_pan(
            texts,
            skip_keywords_enabled=True,
            aadhaar_confirmed=False,
        )

        skip_reason = checks.get("skip_reason")
        pan_found = bool(checks.get("pan_found", False))
        yolo_report = {
            "is_aadhaar": 0,
            "is_number": 0,
            "is_number_masked": 0,
            "is_qr": 0,
            "is_qr_masked": 0,
            "is_xx": 0,
        }

        detected_words = []
        final_form = oriented.copy()
        if not checks["skipped"]:
            detected_words = find_aadhaar_patterns(tokens_list)
            patterns_overlay = _draw_detected_words(oriented, detected_words, (0, 140, 255), "FORM OCR PATTERNS")
            _save_image(folders["card"] / "450_card_ocr_patterns_overlay.png", patterns_overlay)
            final_form = mask_ocr_detections(oriented.copy(), detected_words, tokens_list)
            _save_image(folders["card"] / "460_after_ocr_mask.png", final_form)
        else:
            _na_marker(folders["card"] / "450_card_ocr_patterns_overlay_not_applicable.json", "form_lane_skipped_before_pattern_mask")
            _save_image(folders["card"] / "460_after_ocr_mask.png", final_form)

        _save_image(folders["card"] / "420_card_ocr_aadhaar_keywords.png", _draw_tokens(oriented, [
            t for t in tokens_list if "aadhaar" in str(t.get("text", "")).lower() or "aadhar" in str(t.get("text", "")).lower()
        ], (0, 255, 255), "FORM OCR AADHAAR KEYWORDS"))
        _save_image(folders["card"] / "430_after_pvc_mask.png", final_form)
        _save_image(folders["card"] / "440_after_yolo_mask.png", final_form)
        _save_json(folders["card"] / "470_rotate_back_info.json", {
            "best_angle": 0,
            "inverse_angle_applied": 0,
            "rotation_applied": False,
            "note": "form_lane",
        })
        _save_image(folders["card"] / "499_final.png", final_form)

        _save_json(
            folders["crops"] / "320_crops_index.json",
            {
                "not_applicable_reason": "form_lane_has_no_aadhaar_crops_before_card_ocr_prep",
                "crops": [],
            },
        )

        token_polygons = [t.get("coordinates", []) for t in tokens_list if t.get("coordinates")]
        token_aabb = []
        for idx, t in enumerate(tokens_list, start=1):
            if not t.get("coordinates"):
                continue
            x1, y1, x2, y2 = _bbox_from_poly(t["coordinates"])
            token_aabb.append({"token_index": idx, "text": t.get("text", ""), "aabb": [x1, y1, x2, y2]})

        mask_regions = []
        for idx, dw in enumerate(detected_words, start=1):
            coords = dw.get("coordinates", [])
            if not coords:
                continue
            x1, y1, x2, y2 = _bbox_from_poly(coords)
            mask_regions.append({"mask_index": idx, "type": dw.get("type", ""), "aabb": [x1, y1, x2, y2], "polygon": coords})

        alignment_diff = []
        for token in token_aabb:
            a = token["aabb"]
            a_area = _box_area(a)
            best_overlap = 0.0
            best_mask_idx = None
            for m in mask_regions:
                ov = _rect_intersection(a, m["aabb"])
                if ov > best_overlap:
                    best_overlap = ov
                    best_mask_idx = m["mask_index"]
            ratio = (best_overlap / a_area) if a_area > 0 else 0.0
            alignment_diff.append({
                "token_index": token["token_index"],
                "best_mask_index": best_mask_idx,
                "token_area": a_area,
                "best_overlap": best_overlap,
                "overlap_ratio": ratio,
            })

        _save_json(folders["reports"] / "910_model_findings.json", {
            "lane": "form",
            "angles": [],
            "winner": None,
            "router": router_result,
        })
        _save_json(folders["reports"] / "920_orientation_scores.json", {"angles": [], "winner_angle": 0})
        _save_json(folders["reports"] / "930_token_polygons.json", {"tokens": token_polygons})
        _save_json(folders["reports"] / "931_token_aabb.json", {"tokens": token_aabb})
        _save_json(folders["reports"] / "940_mask_regions.json", {"mask_regions": mask_regions})
        _save_json(folders["reports"] / "950_alignment_diff.json", {"alignment": alignment_diff})

        report = _build_db_parity_report(
            input_path=input_path,
            lane="form",
            winner_angle=0,
            skip_reason=skip_reason,
            pan_found=pan_found,
            card_detected=False,
            aadhaar_verified=False,
            yolo_report=yolo_report,
            ocr_patterns_found=len(detected_words),
            total_seconds=time.perf_counter() - t_total_start,
            orientation_scores=orientation_scores,
        )
        report["router"] = router_result
        report["ocr_failed"] = bool(ocr_failed)
        report["doc_orientation_failed"] = bool(doc_orientation_failed)
        _save_json(folders["reports"] / "900_report.json", report)

    else:
        # NOTE: Card/uncertain lane full forensic path.
        oriented = winner_data.get("rotated", image.copy())
        gate_result = winner_data
        _save_json(
            folders["winner"] / "300_best_angle.json",
            {
                "best_angle": int(winner_angle),
                "winner_score": float(winner_data.get("score", 0.0)),
            },
        )
        _save_image(folders["winner"] / "310_oriented_best.png", oriented)

        merged_dets = gate_result.get("merged_dets", [])
        pre_mask_boxes = [
            {
                "box": [int(d["box"][0]), int(d["box"][1]), int(d["box"][2]), int(d["box"][3])],
                "label": f"{d.get('label', '')}:{float(d.get('conf', 0.0)):.2f}",
            }
            for d in merged_dets
        ]
        stage_gate = _draw_boxes(oriented, pre_mask_boxes, (160, 0, 200), "GATE MERGED DETECTIONS")
        _save_image(folders["winner"] / "312_gate_merged_detections.png", stage_gate)

        aadhaar_box_items = []
        for idx, box in enumerate(gate_result.get("aadhaar_boxes", []) or []):
            aadhaar_box_items.append(
                {
                    "box": [int(box[0]), int(box[1]), int(box[2]), int(box[3])],
                    "label": f"aadhaar_box_{idx+1}",
                }
            )
        stage_aadhaar_boxes = _draw_boxes(oriented, aadhaar_box_items, (0, 255, 255), "AADHAAR CARD BOXES")
        _save_image(folders["winner"] / "313_gate_aadhaar_boxes.png", stage_aadhaar_boxes)

        # NOTE: Emit crop forensic package before OCR prep.
        crop_index = []
        for crop_info in gate_result.get("aadhaar_crops", []) or []:
            cidx = int(crop_info.get("crop_index", len(crop_index) + 1))
            crop_dir = folders["crops"] / f"crop_{cidx:02d}"
            crop_dir.mkdir(parents=True, exist_ok=True)

            cbox = crop_info.get("crop_box", [0, 0, 0, 0])
            x1, y1, x2, y2 = [int(v) for v in cbox]
            h, w = oriented.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            bbox_on_winner = oriented.copy()
            cv2.rectangle(bbox_on_winner, (x1, y1), (x2, y2), (0, 255, 255), 2)
            _save_image(crop_dir / "321_crop_bbox_on_winner.png", bbox_on_winner)

            crop_raw = oriented[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else np.zeros((10, 10, 3), dtype=np.uint8)
            _save_image(crop_dir / "322_crop_raw.png", crop_raw)

            main_inside = crop_info.get("main_inside", [])
            best_inside = crop_info.get("best_inside", [])
            merged_inside = crop_info.get("merged_inside", [])

            main_inside_rel = [
                {**d, "box": [d["box"][0] - x1, d["box"][1] - y1, d["box"][2] - x1, d["box"][3] - y1]}
                for d in main_inside
            ]
            best_inside_rel = [
                {**d, "box": [d["box"][0] - x1, d["box"][1] - y1, d["box"][2] - x1, d["box"][3] - y1]}
                for d in best_inside
            ]
            merged_inside_rel = [
                {**d, "box": [d["box"][0] - x1, d["box"][1] - y1, d["box"][2] - x1, d["box"][3] - y1]}
                for d in merged_inside
            ]

            _save_image(
                crop_dir / "323_crop_main_inside.png",
                _draw_boxes(
                    crop_raw,
                    [{"box": [int(b["box"][0]), int(b["box"][1]), int(b["box"][2]), int(b["box"][3])], "label": b.get("label", "")} for b in main_inside_rel],
                    (255, 120, 0),
                    "MAIN INSIDE",
                ),
            )
            _save_image(
                crop_dir / "324_crop_best_inside.png",
                _draw_boxes(
                    crop_raw,
                    [{"box": [int(b["box"][0]), int(b["box"][1]), int(b["box"][2]), int(b["box"][3])], "label": b.get("label", "")} for b in best_inside_rel],
                    (0, 255, 120),
                    "BEST INSIDE",
                ),
            )
            _save_image(
                crop_dir / "325_crop_merged_inside.png",
                _draw_boxes(
                    crop_raw,
                    [{"box": [int(b["box"][0]), int(b["box"][1]), int(b["box"][2]), int(b["box"][3])], "label": b.get("label", "")} for b in merged_inside_rel],
                    (180, 0, 220),
                    "MERGED INSIDE",
                ),
            )

            findings = {
                "crop_index": cidx,
                "crop_box": cbox,
                "fb_classes": crop_info.get("fb_classes", []),
                "counts": {
                    "main_inside": _count_labels(main_inside),
                    "best_inside": _count_labels(best_inside),
                    "merged_inside": _count_labels(merged_inside),
                },
            }
            _save_json(crop_dir / "326_crop_findings.json", findings)
            crop_index.append({"crop_index": cidx, "crop_box": cbox})

        _save_json(folders["crops"] / "320_crops_index.json", {"crops": crop_index})

        work_img, all_texts, all_boxes, all_confidences, ocr_failed, doc_orientation_failed, aadhaar_crops = _run_ocr_for_card_path(
            oriented.copy(), ocr, gate_result
        )
        _save_image(folders["card"] / "400_after_card_ocr_prep.png", work_img)

        tokens_list = _tokens_from_ocr(all_texts, all_boxes, all_confidences)
        all_tokens_overlay = _draw_tokens(work_img, tokens_list, (0, 220, 0), "CARD OCR TOKENS AXIS")
        _save_image(folders["card"] / "410_card_ocr_tokens_axis.png", all_tokens_overlay)
        token_poly_overlay = _draw_token_polygons(work_img, tokens_list, (220, 200, 0), "CARD OCR TOKENS POLYGON")
        _save_image(folders["card"] / "411_card_ocr_tokens_polygon.png", token_poly_overlay)

        aadhaar_kw_tokens = [
            t for t in tokens_list
            if "aadhaar" in str(t.get("text", "")).lower() or "aadhar" in str(t.get("text", "")).lower()
        ]
        kw_overlay = _draw_tokens(work_img, aadhaar_kw_tokens, (0, 255, 255), "CARD OCR AADHAAR KEYWORDS")
        _save_image(folders["card"] / "420_card_ocr_aadhaar_keywords.png", kw_overlay)

        aadhaar_confirmed = bool(aadhaar_crops) and is_aadhaar_card_confirmed(all_texts)
        checks = _verify_skip_pan(
            all_texts,
            skip_keywords_enabled=True,
            aadhaar_confirmed=aadhaar_confirmed,
        )
        yolo_report = {
            "is_aadhaar": 0,
            "is_number": 0,
            "is_number_masked": 0,
            "is_qr": 0,
            "is_qr_masked": 0,
            "is_xx": 0,
        }
        detected_words = []
        rotate_back_info = {
            "best_angle": int(winner_angle),
            "inverse_angle_applied": 0,
            "rotation_applied": False,
        }

        if checks["skipped"]:
            # Keep parity with core.pipeline: include detected YOLO counts even when
            # skip/PAN short-circuits masking.
            yolo_report = _derive_yolo_report_from_dets(gate_result.get("merged_dets", []))
            _save_image(folders["card"] / "430_after_pvc_mask.png", work_img)
            _save_image(folders["card"] / "440_after_yolo_mask.png", work_img)
            _save_image(folders["card"] / "450_card_ocr_patterns_overlay.png", work_img)
            _save_image(folders["card"] / "460_after_ocr_mask.png", work_img)
            # Mirror core.pipeline skip-path: rotate back to original orientation before saving final.
            skip_final = work_img
            if winner_angle != 0:
                skip_final = rotate_back_to_original_space(skip_final, int(winner_angle), original_shape)
                rotate_back_info["inverse_angle_applied"] = int(-winner_angle)
                rotate_back_info["rotation_applied"] = True
            _save_image(folders["card"] / "499_final.png", skip_final)
        else:
            after_pvc = work_img.copy()
            if aadhaar_crops:
                after_pvc, pvc_stats = mask_pvc_aadhaar(after_pvc, aadhaar_crops)
            else:
                pvc_stats = {"pvc_cards_processed": 0, "pvc_cards_masked": 0}
            _save_image(folders["card"] / "430_after_pvc_mask.png", after_pvc)

            # NOTE: Match core.pipeline PAN-safe QR masking gate.
            merged_dets = gate_result.get("merged_dets", [])
            has_primary_number_det = any(
                str(d.get("label", "")).lower() in {"number", "number_inverse", "number_anticlockwise"}
                and float(d.get("conf", 0.0)) > 0.3
                for d in merged_dets
            )
            qr_masking_allowed = bool(aadhaar_confirmed) or has_primary_number_det

            after_yolo, yolo_report = mask_yolo_detections(
                after_pvc.copy(),
                merged_dets,
                debug=True,
                stats={},
                ocr=ocr,
                aadhaar_boxes=(gate_result.get("aadhaar_boxes") if qr_masking_allowed else []),
            )
            _save_image(folders["card"] / "440_after_yolo_mask.png", after_yolo)

            detected_words = find_aadhaar_patterns(tokens_list)
            pattern_overlay = _draw_detected_words(after_yolo, detected_words, (0, 140, 255), "CARD OCR PATTERNS")
            _save_image(folders["card"] / "450_card_ocr_patterns_overlay.png", pattern_overlay)

            after_ocr = mask_ocr_detections(after_yolo.copy(), detected_words, tokens_list)
            _save_image(folders["card"] / "460_after_ocr_mask.png", after_ocr)

            final_img = after_ocr
            if winner_angle != 0:
                final_img = rotate_back_to_original_space(final_img, int(winner_angle), original_shape)
                rotate_back_info["inverse_angle_applied"] = int(-winner_angle)
                rotate_back_info["rotation_applied"] = True
            _save_image(folders["card"] / "499_final.png", final_img)

        _save_json(folders["card"] / "470_rotate_back_info.json", rotate_back_info)

        token_polygons = [t.get("coordinates", []) for t in tokens_list if t.get("coordinates")]
        token_aabb = []
        for idx, t in enumerate(tokens_list, start=1):
            if not t.get("coordinates"):
                continue
            x1, y1, x2, y2 = _bbox_from_poly(t["coordinates"])
            token_aabb.append({"token_index": idx, "text": t.get("text", ""), "aabb": [x1, y1, x2, y2]})

        mask_regions = []
        for det_idx, d in enumerate(gate_result.get("merged_dets", []), start=1):
            box = d.get("box", [0, 0, 0, 0])
            mask_regions.append(
                {
                    "mask_index": det_idx,
                    "source": "yolo",
                    "type": str(d.get("label", "")).lower(),
                    "aabb": [int(box[0]), int(box[1]), int(box[2]), int(box[3])],
                }
            )
        for idx, dw in enumerate(detected_words, start=1):
            coords = dw.get("coordinates", [])
            if not coords:
                continue
            x1, y1, x2, y2 = _bbox_from_poly(coords)
            mask_regions.append(
                {
                    "mask_index": 1000 + idx,
                    "source": "ocr",
                    "type": dw.get("type", ""),
                    "aabb": [x1, y1, x2, y2],
                    "polygon": coords,
                }
            )

        alignment_diff = []
        for token in token_aabb:
            a = token["aabb"]
            a_area = _box_area(a)
            best_overlap = 0.0
            best_mask_idx = None
            for m in mask_regions:
                ov = _rect_intersection(a, m["aabb"])
                if ov > best_overlap:
                    best_overlap = ov
                    best_mask_idx = m["mask_index"]
            ratio = (best_overlap / a_area) if a_area > 0 else 0.0
            alignment_diff.append(
                {
                    "token_index": token["token_index"],
                    "best_mask_index": best_mask_idx,
                    "token_area": a_area,
                    "best_overlap": best_overlap,
                    "overlap_ratio": ratio,
                }
            )

        _save_json(
            folders["reports"] / "910_model_findings.json",
            {
                "lane": lane,
                "angles": model_findings["angles"],
                "winner_angle": int(winner_angle),
                "winner_counts": {
                    "main": _count_labels(gate_result.get("main_dets", [])),
                    "fb_filtered": _count_labels(gate_result.get("fb_filtered", [])),
                    "best": _count_labels(gate_result.get("best_dets_full", [])),
                    "merged": _count_labels(gate_result.get("merged_dets", [])),
                },
            },
        )
        _save_json(folders["reports"] / "920_orientation_scores.json", {
            "angles": orientation_scores,
            "winner_angle": int(winner_angle),
        })
        _save_json(folders["reports"] / "930_token_polygons.json", {"tokens": token_polygons})
        _save_json(folders["reports"] / "931_token_aabb.json", {"tokens": token_aabb})
        _save_json(folders["reports"] / "940_mask_regions.json", {"mask_regions": mask_regions})
        _save_json(folders["reports"] / "950_alignment_diff.json", {"alignment": alignment_diff})

        report = _build_db_parity_report(
            input_path=input_path,
            lane=lane,
            winner_angle=int(winner_angle),
            skip_reason=checks.get("skip_reason"),
            pan_found=bool(checks.get("pan_found", False)),
            card_detected=bool(aadhaar_crops),
            aadhaar_verified=bool(aadhaar_confirmed),
            yolo_report=yolo_report,
            ocr_patterns_found=len(detected_words),
            total_seconds=time.perf_counter() - t_total_start,
            orientation_scores=orientation_scores,
        )
        report["router"] = router_result
        report["ocr_failed"] = bool(ocr_failed)
        report["doc_orientation_failed"] = bool(doc_orientation_failed)
        report["winner_score"] = float(winner_data.get("score", 0.0))
        _save_json(folders["reports"] / "900_report.json", report)

    logging.getLogger(__name__).info(
        f"visualizer complete: out_dir={folders['run_root']} total_seconds={round(time.perf_counter() - t_total_start, 4)}"
    )
    _detach_file_logger(root_logger, file_handler)

    return folders["run_root"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--out", required=True, help="Output directory for stage images")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out)
    run_root = run_debug(input_path, out_dir)
    print(f"Saved stage artifacts to: {run_root}")


if __name__ == "__main__":
    main()
