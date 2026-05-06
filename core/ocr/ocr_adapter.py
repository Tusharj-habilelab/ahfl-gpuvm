# Migrated from: paddleocr_integration/paddle_ocr_adapter.py (AHFL-Masking 1.0)
# Role: Normalises PaddleOCR v2/v3 output into a unified format consumed by core/masking.py.
#        Engine-agnostic name chosen so this adapter can be swapped for future OCR engines.
"""
ocr_adapter.py — Format Adapter for PaddleOCR Output (AHFL-Masking 1.1)

PaddleOCR v3.x returns results in a DIFFERENT format than EasyOCR.
This adapter normalizes the output so all masking logic in core/masking.py
works unchanged regardless of the OCR engine version.
"""


import logging

log = logging.getLogger(__name__)


def _normalize_bbox(bbox):
    """Convert a PaddleOCR bbox/polygon into four (x, y) float tuples."""
    if bbox is None:
        return None
    points = []
    try:
        for point in bbox:
            if len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
    except (TypeError, ValueError) as e:
        log.warning(f"Failed to normalize bbox {bbox}: {e}")
        return None
    if len(points) >= 4:
        return points[:4]
    return None


def _append_v3_result(adapted, result_dict):
    """Handle PaddleOCR v3 result objects/dicts with rec_texts/rec_scores/rec_polys."""
    if not isinstance(result_dict, dict):
        return
    rec_texts = result_dict.get("rec_texts") or []
    rec_scores = result_dict.get("rec_scores") or []
    rec_polys = result_dict.get("rec_polys") or result_dict.get("dt_polys") or []
    if not rec_texts or not rec_polys:
        return
    for idx, text in enumerate(rec_texts):
        bbox = rec_polys[idx] if idx < len(rec_polys) else None
        bbox_tuples = _normalize_bbox(bbox)
        if not bbox_tuples:
            continue
        score = rec_scores[idx] if idx < len(rec_scores) else 0.0
        try:
            confidence = float(score)
        except (TypeError, ValueError) as e:
            log.warning(f"Failed to parse confidence score {score}: {e}")
            confidence = 0.0
        adapted.append((bbox_tuples, str(text).strip(), confidence))


def adapt_paddle_result(paddle_result):
    """
    Convert PaddleOCR output to a unified format.

    Returns:
        List of tuples: [(bbox, text, confidence), ...]
        where bbox = [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
    """
    adapted = []
    if paddle_result is None:
        return adapted

    if hasattr(paddle_result, "res"):
        _append_v3_result(adapted, getattr(paddle_result, "res"))
        return adapted

    if isinstance(paddle_result, dict):
        _append_v3_result(adapted, paddle_result.get("res", paddle_result))
        return adapted

    for page in paddle_result:
        if page is None:
            continue
        if hasattr(page, "res"):
            _append_v3_result(adapted, getattr(page, "res"))
            continue
        if isinstance(page, dict):
            _append_v3_result(adapted, page.get("res", page))
            continue
        for detection in page:
            try:
                bbox = detection[0]
                text_info = detection[1]
                if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                    text = str(text_info[0])
                    confidence = float(text_info[1])
                elif isinstance(text_info, str):
                    text = text_info
                    confidence = 0.0
                elif isinstance(text_info, dict):
                    text = str(text_info.get('text', text_info.get('rec_text', '')))
                    confidence = float(text_info.get('score', text_info.get('rec_score', 0.0)))
                else:
                    text = str(text_info)
                    confidence = 0.0
                bbox_tuples = [(float(point[0]), float(point[1])) for point in bbox]
                adapted.append((bbox_tuples, text, confidence))
            except (IndexError, TypeError, ValueError) as e:
                log.debug(f"Skipped malformed detection: {e}")
                continue

    log.debug(f"adapt_paddle_result: {len(adapted)} tokens adapted")
    return adapted


def get_texts_and_boxes(adapted_results):
    """
    Extract text strings, bounding boxes, and confidence scores from adapted results.

    Args:
        adapted_results: Output from adapt_paddle_result()

    Returns:
        texts, boxes, confidences
    """
    texts = [r[1] for r in adapted_results]
    boxes = [r[0] for r in adapted_results]
    confidences = [r[2] for r in adapted_results]
    return texts, boxes, confidences
