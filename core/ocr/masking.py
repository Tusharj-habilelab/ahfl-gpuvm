# Migrated from: paddleocr_integration/masking_functions.py (AHFL-Masking 1.0)
# Role: Canonical shared masking logic — Verhoeff validation, OCR pattern matching,
#        YOLO IoU merging, and all image masking operations.
#        In 1.0 this logic was copy-pasted across process_image.py and bulk.py.
#        This is now the SINGLE SOURCE OF TRUTH imported by all services.
"""
masking.py — Core Aadhaar masking logic for AHFL-Masking 1.1 (PaddleOCR).

Contains:
  - Verhoeff algorithm for Aadhaar number validation
  - Cosine similarity & Levenshtein distance for fuzzy text matching
  - Pattern matching to identify Aadhaar numbers (12-digit, split 4-4-4, etc.)
  - YOLO detection merging (IoU-based deduplication for dual model pipeline)
  - OCR text masking (black rectangles over sensitive data)
  - YOLO bounding-box masking (for detected Number/QR regions)
"""

import re
import math
import time
import logging
import cv2
import numpy as np
from collections import Counter
from core.ocr.ocr_adapter import adapt_paddle_result, get_texts_and_boxes

log = logging.getLogger(__name__)


# ============================================================
# Verhoeff Algorithm Tables (for Aadhaar number validation)
# ============================================================

d_table = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
]

p_table = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
]

inv_table = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


# ============================================================
# Validation Functions
# ============================================================

def verhoeff_validate(number: str) -> bool:
    """Validate a 12-digit Aadhaar number using the Verhoeff algorithm."""
    hyphen_count = number.count('-')
    if hyphen_count > 1:
        return False
    number = number.replace('-', '').replace(' ', '')
    if not number.isdigit() or len(number) != 12:
        return False
    if any(number.count(digit) > 4 for digit in set(number)):
        return False
    c = 0
    reversed_digits = list(map(int, reversed(number)))
    for i, digit in enumerate(reversed_digits):
        c = d_table[c][p_table[i % 8][digit]]
    return c == 0


def is_valid_aadhaar_number(number: str) -> bool:
    """
    Full Aadhaar number validation (UIDAI structural rules + Verhoeff).

    Checks:
      1. Exactly 12 digits (after stripping hyphens/spaces)
      2. First digit is 2-9 (UIDAI rule — 0 and 1 are reserved)
      3. No single digit repeats more than 4 times
      4. Verhoeff checksum passes

    Args:
        number: Raw string (may contain hyphens/spaces).

    Returns:
        True if all validations pass.
    """
    cleaned = number.replace('-', '').replace(' ', '')
    if not cleaned.isdigit() or len(cleaned) != 12:
        return False
    # First digit must be 2-9 (UIDAI specification)
    if cleaned[0] in ('0', '1'):
        return False
    return verhoeff_validate(number)


def compute_digit_mask_region(
    box: list, mask_digits: int = 8, total_digits: int = 12, reverse: bool = False
) -> tuple:
    """
    Compute the sub-region covering the first N digits of a number bbox.

    FALLBACK masking when OCR cannot read individual digit positions.
    Masks a proportional fraction (8/12 = 0.667) of the bounding box.

        Handles both horizontal and vertical number orientations:
            - Horizontal: mask left portion (width-based)
            - Vertical: mask top portion (height-based)
        For 180°-read labels (e.g. Number_anticlockwise), set reverse=True
        to mask from the opposite side while still targeting original first 8 digits.

    Args:
        box: [x1, y1, x2, y2] bounding box of the full number.
        mask_digits: Number of digits to mask (default 8).
        total_digits: Total digits in number (default 12).

    Returns:
        (x1, y1, x2_mask, y2_mask) — the region to black out.
    """
    x1, y1, x2, y2 = [int(c) for c in box]
    # Shift mask window by 3px left to catch the first digit fully, and trim
    # 3px from the right edge to keep net mask width stable.
    x1 = max(0, x1 - 3)
    x2 = max(x1 + 1, x2 - 3)
    w = x2 - x1
    h = y2 - y1
    fraction = mask_digits / total_digits

    if w > h:
        if reverse:
            # Reverse path: mask right portion (for 180°-read labels).
            x1_mask = int(x2 - fraction * w)
            return (x1_mask, y1, x2, y2)
        # Horizontal number: mask left portion
        x2_mask = int(x1 + fraction * w)
        return (x1, y1, x2_mask, y2)
    else:
        if reverse:
            # Reverse path: mask bottom portion (for 180°-read labels).
            y1_mask = int(y2 - fraction * h)
            return (x1, y1_mask, x2, y2)
        # Vertical number: mask top portion
        y2_mask = int(y1 + fraction * h)
        return (x1, y1, x2, y2_mask)


# ============================================================
# Text Similarity Functions
# ============================================================

def cosine_similarity(str1: str, str2: str) -> float:
    """Calculate cosine similarity between two strings."""
    str1, str2 = str1.lower(), str2.lower()
    len1, len2 = len(str1), len(str2)
    if len1 > len2:
        len1, len2 = len2, len1
    if len2 == 0 or len1 / len2 <= 0.5:
        return 0.0
    vec1, vec2 = Counter(str1), Counter(str2)
    dot_product = sum(vec1[c] * vec2[c] for c in set(vec1) & set(vec2))
    mag1 = math.sqrt(sum(count ** 2 for count in vec1.values()))
    mag2 = math.sqrt(sum(count ** 2 for count in vec2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)


def levenshtein_score(str1: str, str2: str) -> float:
    """Calculate normalized Levenshtein similarity score (1.0 = identical)."""
    str1, str2 = str1.lower(), str2.lower()
    m, n = len(str1), len(str2)
    if m == 0 or n == 0:
        return 0.0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if str1[i - 1] == str2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return 1 - dp[m][n] / max(m, n)


# ============================================================
# Number Pattern Helpers
# ============================================================

def is_four_digit_number(s: str) -> bool:
    hyphen_count = s.count('-')
    if hyphen_count > 1:
        return False
    s = s.replace('-', '').replace(' ', '')
    return bool(re.fullmatch(r'\d{4}', s))


def is_twelve_digit_number(s: str) -> bool:
    hyphen_count = s.count('-')
    if hyphen_count > 1:
        return False
    s = s.replace('-', '').replace(' ', '')
    return bool(re.fullmatch(r'\d{12}', s))


# OCR handwriting/scan noise map for digit recovery in form-lane Aadhaar patterns.
_OCR_DIGIT_NOISE_TRANSLATION = str.maketrans({
    "o": "0", "O": "0", "D": "0", "Q": "0",
    "i": "1", "I": "1", "l": "1", "L": "1", "|": "1", "!": "1",
    "z": "2", "Z": "2",
    "s": "5", "S": "5",
    "g": "6", "G": "6",
    "b": "8", "B": "8",
    "q": "9",
})


def _normalize_ocr_digits(text: str) -> str:
    """Normalize common OCR noise and keep only digits for Aadhaar checks."""
    normalized = str(text or "").translate(_OCR_DIGIT_NOISE_TRANSLATION)
    return re.sub(r"[^0-9]", "", normalized)


def _merge_token_coordinates(tokens_list: list, start_idx: int, end_idx: int):
    """Merge token polygons from [start_idx, end_idx) into one bounding polygon."""
    coords = []
    for idx in range(start_idx, end_idx):
        coords.extend(tokens_list[idx].get("coordinates", []))
    if not coords:
        return None
    x1 = min(p[0] for p in coords)
    y1 = min(p[1] for p in coords)
    x2 = max(p[0] for p in coords)
    y2 = max(p[1] for p in coords)
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def _coords_bbox_key(coords) -> tuple:
    """Create a stable bbox key for simple duplicate suppression."""
    x1 = int(min(p[0] for p in coords))
    y1 = int(min(p[1] for p in coords))
    x2 = int(max(p[0] for p in coords))
    y2 = int(max(p[1] for p in coords))
    return (x1, y1, x2, y2)


def _token_span_is_right_to_left(tokens_list: list, start_idx: int, end_idx: int) -> bool:
    """
    Infer OCR read direction for a token span.

    Returns True when token centers move right->left (or bottom->top for vertical text).
    This lets form-lane recovery mask the original first 8 digits, not the trailing 8.
    """
    centers = []
    for idx in range(start_idx, end_idx):
        coords = tokens_list[idx].get("coordinates", [])
        if not coords:
            continue
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        centers.append(((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0))

    if len(centers) < 2:
        return False

    start_center = centers[0]
    end_center = centers[-1]
    horizontal = abs(end_center[0] - start_center[0]) >= abs(end_center[1] - start_center[1])
    if horizontal:
        return end_center[0] < start_center[0]
    return end_center[1] < start_center[1]


def extract_number_coordinates(text: str, bbox):
    """Extract 12-digit number coordinates from OCR text within a bounding box."""
    match = re.search(r"\b\d{12}\b", text)
    if not match:
        return None
    num_start, num_end = match.start(), match.end()
    total_chars = len(text)
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = bbox
    char_width = (x2 - x1) / total_chars if total_chars > 0 else 0
    num_x1 = x1 + num_start * char_width
    num_x2 = x1 + num_end * char_width
    return {"text": match.group(), "coordinates": [(num_x1, y1), (num_x2, y2), (num_x2, y3), (num_x1, y4)]}


def extract_target_coordinates(text: str, bbox, target_text: str):
    """Extract target keyword coordinates from OCR text within a bounding box."""
    text, target_text = text.lower(), target_text.lower()
    new_text = ""
    for ch in text:
        if ('a' <= ch <= 'z') or ch in (' ', '.', ':'):
            new_text += ch
        else:
            new_text += ch * 2
    match = re.search(re.escape(target_text), new_text)
    if not match:
        return None
    target_start, target_end = match.start(), match.end()
    total_chars = len(new_text)
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = bbox
    char_width = (x2 - x1) / total_chars if total_chars > 0 else 0
    target_x1 = x1 + target_start * char_width
    target_x2 = x1 + target_end * char_width
    return {"text": match.group(), "coordinates": [(target_x1, y1), (target_x2, y2), (target_x2, y3), (target_x1, y4)]}


def uid_table_masking_coordinates(x1: float, x2: float, y1: float, y2: float, tokens_list: list) -> float:
    """
    Dynamically find the bottom of a UID table by scanning OCR tokens for overlap.

    Used by aadhaar_uid and aadhar_table_pmy_hw masking to extend the mask
    rectangle down to the last row of the UID table instead of using a fixed offset.

    Args:
        x1, x2, y1, y2: Initial mask bounding box (float pixel coords).
        tokens_list: OCR tokens with 'coordinates' key (list of (x,y) tuples).

    Returns:
        y2_ans: Float — bottom edge of the lowest overlapping token row.
        If no tokens overlap, returns y1 (no extension).
    """
    y2_ans = y1
    for token in tokens_list:
        coords = token["coordinates"]
        x1_new = min(p[0] for p in coords)
        x2_new = max(p[0] for p in coords)
        y1_new = min(p[1] for p in coords)
        y2_new = max(p[1] for p in coords)
        area2 = abs(x2_new - x1_new) * abs(y2_new - y1_new)
        if area2 == 0:
            continue
        overlap_x1 = max(x1, x1_new)
        overlap_y1 = max(y1, y1_new)
        overlap_x2 = min(x2, x2_new)
        overlap_y2 = min(y2, y2_new)
        if overlap_x1 < overlap_x2 and overlap_y1 < overlap_y2:
            overlap_area = abs(overlap_x2 - overlap_x1) * abs(overlap_y2 - overlap_y1)
            if overlap_area > 0.5 * area2:
                y2_ans = max(y2_ans, y1_new, y2_new)
    return y2_ans


# ============================================================
# IoU-Based Detection Merging (for Dual YOLO Model Pipeline)
# ============================================================

def calculate_iou(box1, box2):
    """
    Calculate IoU between two boxes in [x1, y1, x2, y2] format.
    Returns 0.0 (no overlap) to 1.0 (perfect overlap).
    """
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    if union == 0:
        return 0.0
    return intersection / union


def _detection_family(label: str) -> str:
    """Group labels that represent the same physical target for safe deduping."""
    normalized = str(label or "").lower()
    if normalized in {"number", "number_anticlockwise", "number_inverse", "is_number"}:
        return "number"
    if normalized in {"qr", "is_qr"}:
        return "qr"
    return normalized


def _label_implies_reverse_mask(label: str) -> bool:
    """Return True when label semantics imply reverse first-8 masking direction."""
    return str(label or "").lower() == "number_anticlockwise"


def _deduplicate_overlapping_detections(detections, iou_threshold=0.5):
    """
    Collapse overlapping detections from the same physical target.

    This is needed in two places:
      1. main.pt can emit both number and number_anticlockwise on the same strip.
      2. overlapping Aadhaar crops can re-add the same number/QR region multiple times.
    """
    # Labels that trigger masking actions (from main.pt)
    _PRIMARY_LABELS = {"number", "number_anticlockwise", "number_inverse", "qr"}
    # Labels that confirm detections but do not drive masking (from best.pt)
    _HELPER_LABELS = {"is_number", "is_qr"}

    deduped = []
    for candidate in detections:
        candidate_copy = dict(candidate)
        candidate_label = candidate_copy.get("label", "")
        candidate_family = _detection_family(candidate_label)
        # Keep orientation hint independent of final label chosen by confidence merge.
        candidate_copy["reverse_mask"] = bool(candidate_copy.get("reverse_mask", False)) or _label_implies_reverse_mask(candidate_label)
        merged_into_existing = False

        for existing in deduped:
            existing_label = existing.get("label", "")
            if _detection_family(existing_label) != candidate_family:
                continue
            if calculate_iou(existing["box"], candidate_copy["box"]) <= iou_threshold:
                continue

            # Keep the stronger detection, but never let helper labels overwrite
            # actionable primary labels for the same physical target.
            if candidate_copy.get("conf", 0.0) > existing.get("conf", 0.0):
                saved_label = existing_label
                saved_reverse = bool(existing.get("reverse_mask", False)) or _label_implies_reverse_mask(saved_label)
                existing.clear()
                existing.update(candidate_copy)
                if saved_label in _PRIMARY_LABELS and candidate_label in _HELPER_LABELS:
                    existing["label"] = saved_label
                # Preserve reverse direction if either side indicated anticlockwise semantics.
                existing["reverse_mask"] = bool(existing.get("reverse_mask", False)) or saved_reverse
            else:
                # Preserve reverse direction even when candidate loses confidence comparison.
                existing["reverse_mask"] = bool(existing.get("reverse_mask", False)) or bool(candidate_copy.get("reverse_mask", False))
            merged_into_existing = True
            break

        if not merged_into_existing:
            deduped.append(candidate_copy)

    return deduped


def merge_detections(detections1, detections2, iou_threshold=0.5):
    """
    Merge detections from two YOLO models, removing duplicates via IoU.
    Each detection: {"box": [x1,y1,x2,y2], "label": str, "conf": float, "model": str}

    Primary labels (from main.pt) drive masking actions: "number", "number_anticlockwise",
    "number_inverse". Helper labels (from best.pt) confirm detections: "is_number", "is_qr".
    When a helper label wins the confidence race, we keep its higher confidence but restore
    the primary label — otherwise masking skips the region thinking it is unverified.
    """
    # Labels that trigger masking actions (from main.pt)
    _PRIMARY_LABELS = {"number", "number_anticlockwise", "number_inverse"}
    # Labels that confirm detections but do not drive masking (from best.pt)
    _HELPER_LABELS = {"is_number", "is_qr"}

    # Dedup main.pt self-overlaps first — this prevents one strip from surviving
    # as both number and number_anticlockwise before best.pt merge even begins.
    merged = _deduplicate_overlapping_detections(detections1, iou_threshold=iou_threshold)
    for det2 in detections2:
        is_duplicate = False
        for det1 in merged:
            if _detection_family(det1.get("label", "")) != _detection_family(det2.get("label", "")):
                continue
            if calculate_iou(det1["box"], det2["box"]) > iou_threshold:
                if det2["conf"] > det1["conf"]:
                    # Save primary label before update — best.pt helper labels must not
                    # overwrite main.pt primary labels, or masking will skip the region.
                    saved_label = det1["label"]
                    saved_reverse = bool(det1.get("reverse_mask", False)) or _label_implies_reverse_mask(saved_label)
                    det1.update(det2)  # take best.pt's higher confidence
                    if saved_label in _PRIMARY_LABELS and det2["label"] in _HELPER_LABELS:
                        det1["label"] = saved_label  # restore primary label
                    # Preserve reverse direction if existing winner was anticlockwise.
                    det1["reverse_mask"] = bool(det1.get("reverse_mask", False)) or saved_reverse or _label_implies_reverse_mask(det2.get("label", ""))
                else:
                    # Preserve reverse direction even when det2 is not chosen as winner.
                    det1["reverse_mask"] = bool(det1.get("reverse_mask", False)) or _label_implies_reverse_mask(det2.get("label", ""))
                is_duplicate = True
                break
        if not is_duplicate:
            det2_copy = dict(det2)
            det2_copy["reverse_mask"] = bool(det2_copy.get("reverse_mask", False)) or _label_implies_reverse_mask(det2_copy.get("label", ""))
            merged.append(det2_copy)

    # Dedup once more after cross-model merge so overlapping Aadhaar crops do not
    # leave repeated number/QR detections in the final merged list.
    return _deduplicate_overlapping_detections(merged, iou_threshold=iou_threshold)


def yolo_results_to_detections(results, model_name="model"):
    """Convert Ultralytics YOLO results to a list of detection dicts."""
    detections = []
    boxes = results.boxes
    for i in range(len(boxes)):
        box = boxes.xyxy[i].tolist()
        label = results.names[int(boxes.cls[i])]
        conf = float(boxes.conf[i])
        detections.append({"box": box, "label": label, "conf": conf, "model": model_name})
    return detections


# ============================================================
# YOLO-Based Masking (Black rectangles on Number/QR regions)
# ============================================================

def check_image_text(image, coordinates, label, stats=None, ocr=None):
    """Check if a detected region contains 'x', 'y', or 'k' (already masked indicator).

    Args:
        image: BGR numpy array.
        coordinates: [x1, y1, x2, y2] bounding box.
        label: Detection label (e.g. 'Number_anticlockwise').
        stats: Optional dict to accumulate timing stats.
        ocr: PaddleOCR instance (reuses caller's singleton; falls back to create_paddle_ocr()).
    """
    start_time = time.perf_counter() if stats is not None else None
    x1, y1, x2, y2 = [int(c) for c in coordinates]
    cropped_img = image[y1:y2, x1:x2]
    if label == 'Number_anticlockwise':
        cropped_img = cv2.rotate(cropped_img, cv2.ROTATE_180)

    try:
        # ocr must always be the shared singleton passed from pipeline.py — never None.
        # Fallback create_paddle_ocr() was removed: it silently loaded a second model into GPU VRAM.
        if ocr is None:
            raise ValueError("ocr must be provided; pass the shared PaddleOCR singleton")
        ocr_result = ocr.ocr(cropped_img)
        adapted = adapt_paddle_result(ocr_result)
        texts, _, _ = get_texts_and_boxes(adapted)
        text = ' '.join(texts) if texts else ""
    except Exception:
        text = ""

    if stats is not None and start_time is not None:
        stats["paddle_ocr_calls"] = stats.get("paddle_ocr_calls", 0) + 1
        stats["paddle_ocr_seconds"] = stats.get("paddle_ocr_seconds", 0.0) + (time.perf_counter() - start_time)

    # NOTE: Previous rule (`x` or `y` or `k` anywhere) caused false positives.
    # Example: OCR noise or random text containing a single 'y' made numbers look
    # "already masked", yielding is_xx>0 and is_number_masked=0.
    # New rule: require a strong mask-like pattern.
    normalized = re.sub(r"\s+", "", text.lower())
    if not normalized:
        return False

    # Common masked token style: 'xxxx' / 'yyyy' / 'kkkk' (at least 4 chars)
    if re.search(r"[xyk]{4,}", normalized):
        return True

    # Fallback heuristic: at least 4 mask chars and >= 60% of token are x/y/k.
    mask_chars = sum(1 for ch in normalized if ch in "xyk")
    return mask_chars >= 4 and (mask_chars / max(len(normalized), 1)) >= 0.60


def _first_8_digit_region_from_ocr_tokens(texts, boxes, crop_w, crop_h, rotated_180=False):
    """
    Derive the exact mask span for the first 8 digits from OCR token bboxes.

    Notes:
    - Uses OCR token coordinates (not char-count fraction).
    - Approximates per-digit centers inside each token bbox by character index.
    - Supports the Number_anticlockwise path by mapping rotated OCR coords
      back to the original crop coordinate system.
    """
    horizontal = crop_w > crop_h
    digit_points = []

    for text, box in zip(texts, boxes):
        token = str(text or "")
        if not token or not box:
            continue

        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        if not xs or not ys:
            continue

        axis_min = float(min(xs) if horizontal else min(ys))
        axis_max = float(max(xs) if horizontal else max(ys))
        token_len = max(1, len(token))
        axis_span = max(1.0, axis_max - axis_min)
        per_char_span = axis_span / token_len

        for idx, ch in enumerate(token):
            if not ch.isdigit():
                continue

            # Center of this character along the main text axis.
            pos = axis_min + ((idx + 0.5) / token_len) * axis_span
            span = per_char_span

            if rotated_180:
                if horizontal:
                    pos = crop_w - pos
                else:
                    pos = crop_h - pos

            digit_points.append((pos, span))

    if len(digit_points) < 8:
        return None

    # NOTE: OCR runs on a 180-rotated crop for Number_anticlockwise.
    # That reverses digit reading order relative to the original image.
    # We must still mask the original FIRST 8 digits, so for rotated crops
    # we select the trailing 8 points from OCR-read order.
    selected_points = digit_points[-8:] if rotated_180 else digit_points[:8]

    starts = [p - (s / 2.0) for p, s in selected_points]
    ends = [p + (s / 2.0) for p, s in selected_points]
    return (min(starts), max(ends), horizontal)


def _ocr_verify_and_mask_number(image, box, label, ocr, stats=None, reverse_hint: bool = False):
    """
    Try to read digits from a YOLO number bbox via OCR and mask first 8 precisely.

    Returns:
        (masked_image, success: bool)
        success=True means OCR read valid 12-digit Aadhaar and masked first 8.
        success=False means OCR failed to read — caller should use fallback.
    """
    x1, y1, x2, y2 = [int(c) for c in box]
    h_img, w_img = image.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w_img, x2), min(h_img, y2)

    if x2 <= x1 or y2 <= y1:
        return image, False

    log.info(f"OCR verify: label={label} box=[{x1},{y1},{x2},{y2}]")

    cropped = image[y1:y2, x1:x2]
    if label.lower() == 'number_anticlockwise':
        cropped = cv2.rotate(cropped, cv2.ROTATE_180)

    try:
        # ocr must always be the shared singleton passed from pipeline.py — never None.
        # Fallback create_paddle_ocr() was removed: it silently loaded a second model into GPU VRAM.
        if ocr is None:
            raise ValueError("ocr must be provided; pass the shared PaddleOCR singleton")
        ocr_result = ocr.ocr(cropped)
        adapted = adapt_paddle_result(ocr_result)
        if not adapted:
            log.info("OCR verify: no adapted result — fallback to proportional mask")
            return image, False

        texts, boxes, _ = get_texts_and_boxes(adapted)
        all_text = ' '.join(texts)

        # Extract digits only
        digits = re.sub(r'[^0-9]', '', all_text)
        log.info(f"OCR verify: read digits={len(digits)} text='{all_text[:40]}'")

        if len(digits) != 12 or not is_valid_aadhaar_number(digits):
            log.info(f"OCR verify: invalid Aadhaar (digits={len(digits)}) — fallback to proportional mask")
            return image, False

        color = (0, 0, 0)

        # Primary: OCR token-bbox based span for first 8 digits.
        # This avoids char-count fraction drift and reduces 9th-digit bleed.
        rotated_180 = (label.lower() == 'number_anticlockwise') or bool(reverse_hint)
        bbox_region = _first_8_digit_region_from_ocr_tokens(
            texts,
            boxes,
            crop_w=cropped.shape[1],
            crop_h=cropped.shape[0],
            rotated_180=rotated_180,
        )

        # Keep existing left-padding rule to catch partially exposed first digit.
        if bbox_region is not None:
            span_start, span_end, horizontal = bbox_region
            if horizontal:
                x1_mask = max(0, int(x1 + span_start) - 3)
                x2_mask = min(w_img, int(x1 + span_end))
                x2_mask = max(x1_mask + 1, x2_mask)
                cv2.rectangle(image, (x1_mask, y1), (x2_mask, y2), color, -1)
                log.info(
                    f"OCR verify: bbox-mask horizontal yolo=[{x1},{y1},{x2},{y2}] "
                    f"ocr_span=({span_start:.1f},{span_end:.1f}) abs=({x1_mask},{x2_mask})"
                )
            else:
                y1_mask = max(0, int(y1 + span_start) - 3)
                y2_mask = min(h_img, int(y1 + span_end))
                y2_mask = max(y1_mask + 1, y2_mask)
                x1_mask = max(0, x1 - 3)
                x2_mask_bound = min(w_img, x2)
                cv2.rectangle(image, (x1_mask, y1_mask), (x2_mask_bound, y2_mask), color, -1)
                log.info(
                    f"OCR verify: bbox-mask vertical yolo=[{x1},{y1},{x2},{y2}] "
                    f"ocr_span=({span_start:.1f},{span_end:.1f}) abs=({y1_mask},{y2_mask})"
                )
        else:
            # Fallback retained: proportional mask when OCR token geometry is insufficient.
            # NOTE: kept for resilience on low-quality scans.
            # For Number_anticlockwise, reverse fallback direction so original first 8 are masked.
            reverse_fallback = (label.lower() == 'number_anticlockwise')
            mask_region = compute_digit_mask_region([x1, y1, x2, y2], reverse=reverse_fallback)
            cv2.rectangle(
                image,
                (mask_region[0], mask_region[1]),
                (mask_region[2], mask_region[3]),
                color,
                -1,
            )
            log.info(
                f"OCR verify: bbox-mask unavailable -> proportional fallback region={mask_region} "
                f"token_count={len(texts)} reverse_hint={reverse_hint}"
            )

        if stats is not None:
            stats["ocr_verified_masks"] = stats.get("ocr_verified_masks", 0) + 1

        return image, True

    except Exception as e:
        log.info(f"OCR verify: exception '{e}' — fallback to proportional mask")
        return image, False


def mask_yolo_detections(image, merged_detections, debug=False, stats=None, ocr=None, aadhaar_boxes=None, gate_fb_confirmed=False):
    """Apply black rectangle masking based on merged YOLO detections.

    Number masking flow:
      1. Check if already masked (check_image_text for x/y/k chars)
      2. Try OCR-verified masking (read digits, validate, mask first 8)
      3. Fallback: proportional width masking (8/12 = 0.667)

    QR masking:
      Spatial check at masking time — only mask QR if inside Aadhaar bbox.
      If aadhaar_boxes is None or empty, QR masking is skipped.

    Args:
        ocr: PaddleOCR instance to reuse (avoids creating new instance per detection).
        aadhaar_boxes: list of [x1,y1,x2,y2] Aadhaar card bboxes for spatial QR check.
    """
    from core.spatial import is_inside_aadhaar_by_area

    color = (0, 0, 0)
    report_data = {
        "is_number": 0, "is_number_masked": 0,
        "is_qr": 0, "is_qr_masked": 0, "is_xx": 0
    }
    for det in merged_detections:
        label = det["label"].lower()
        x1, y1, x2, y2 = [int(c) for c in det["box"]]
        conf = det["conf"]
        if debug:
            log.debug(f"[{det['model']}] {det['label']} conf={conf:.3f} box=[{x1},{y1},{x2},{y2}]")
        log.info(f"YOLO det: [{det['model']}] {det['label']} conf={conf:.2f} box=[{x1},{y1},{x2},{y2}]")
        
        # Skip structural/non-maskable detections: card bbox, already-masked regions, etc.
        if "aadhaar" in label or "masked" in label:
            log.info(f"YOLO det skipped (structural/masked): {det['label']}")
            continue
        
        if "qr" in label and conf > 0.3:
            report_data["is_qr"] += 1
            # Spatial check: only mask QR inside Aadhaar card bbox
            if aadhaar_boxes and is_inside_aadhaar_by_area(det["box"], aadhaar_boxes):
                cv2.rectangle(image, (x1, y1), (x2, y2), color, -1)
                report_data["is_qr_masked"] += 1
                log.info(f"QR masked: box=[{x1},{y1},{x2},{y2}]")
            elif not aadhaar_boxes:
                log.info(f"QR skipped (no Aadhaar bbox): box=[{x1},{y1},{x2},{y2}]")
            else:
                log.info(f"QR skipped (outside Aadhaar bbox): box=[{x1},{y1},{x2},{y2}]")
        elif "number" in label and conf > 0.3:
            report_data["is_number"] += 1
            reverse_hint = bool(det.get("reverse_mask", False))
            try:
                already_masked = check_image_text(image, det["box"], det["label"], stats=stats, ocr=ocr)
            except Exception:
                already_masked = False
            if not already_masked:
                # Primary: OCR-verified digit masking (char-position-aware fraction)
                image, ocr_success = _ocr_verify_and_mask_number(
                    image, det["box"], det["label"], ocr, stats=stats, reverse_hint=reverse_hint
                )
                if not ocr_success:
                    # Safety rule: do NOT fallback-mask weak helper labels (e.g. is_number)
                    # unless OCR verified the Aadhaar number. This blocks large false-positive masks.
                    # Exception: when gate_fb_confirmed=True, the FB/YOLO gate has already
                    # confirmed the page is an Aadhaar card. In that case, proportional fallback
                    # is safe and prevents silently leaving numbers unmasked on real cards.
                    is_primary_number_label = label in {"number", "number_anticlockwise", "number_inverse"}
                    helper_fallback_allowed = bool(gate_fb_confirmed) and bool(aadhaar_boxes) and is_inside_aadhaar_by_area(det["box"], aadhaar_boxes)
                    if is_primary_number_label or helper_fallback_allowed:
                        # Fallback: proportional masking. For Number_anticlockwise,
                        # reverse direction so original first 8 digits remain the masked side.
                        reverse_fallback = (label == "number_anticlockwise") or reverse_hint
                        mask_region = compute_digit_mask_region(det["box"], reverse=reverse_fallback)
                        cv2.rectangle(
                            image,
                            (mask_region[0], mask_region[1]),
                            (mask_region[2], mask_region[3]),
                            color, -1
                        )
                        reason = "primary-label" if is_primary_number_label else "helper-label gate-confirmed"
                        log.info(f"number mask: proportional-fallback ({reason}) label={det['label']} region={mask_region}")
                        report_data["is_number_masked"] += 1
                    else:
                        log.info(
                            f"number skipped (ocr-unverified helper label): label={det['label']} "
                            f"box=[{x1},{y1},{x2},{y2}]"
                        )
                else:
                    report_data["is_number_masked"] += 1
            else:
                log.info(f"number already masked (x/y/k detected): box=[{x1},{y1},{x2},{y2}]")
                report_data["is_xx"] += 1
    log.info(
        f"mask_yolo: number={report_data['is_number']} masked={report_data['is_number_masked']} "
        f"qr={report_data['is_qr']} qr_masked={report_data['is_qr_masked']} xx={report_data['is_xx']}"
    )
    return image, report_data


# ============================================================
# OCR-Based Masking (Pattern matching on extracted text)
# ============================================================

def find_aadhaar_patterns(tokens_list, form_lane_only: bool = False):
    """
    Scan OCR tokens for Aadhaar number patterns.
    Returns a list of detected_words dicts with coordinates and type.
    """
    detected_words = []
    aadhar_found = False
    cersai_found = False
    crif_found = False
    pmay_found = False
    disb_dt_found = False
    loan_code_found = False
    hw_found = False

    for token in tokens_list:
        text = token["text"].strip().lower()
        if "aadhaar" in text or "aadhar" in text:
            aadhar_found = True
        if "cersai" in text:
            cersai_found = True
        if "crif" in text:
            crif_found = True
        if "pmay" in text:
            pmay_found = True

    if cersai_found:
        log.info("C2 FIX: CERSAI keyword detected — skipping masking, report should show skip_reason=cersai_found")
        return detected_words

    n = len(tokens_list)
    for i in range(n):
        if i >= n:
            break
        word = tokens_list[i]["text"]
        next_word = tokens_list[i + 1]["text"] if i + 1 < n else ""
        next_next_word = tokens_list[i + 2]["text"] if i + 2 < n else ""

        if not disb_dt_found and "disb" in word.lower() and "dt" in next_word.lower():
            disb_dt_found = True
        if not loan_code_found and "loan" in word.lower() and "code" in next_word.lower():
            loan_code_found = True
        if not hw_found and disb_dt_found and loan_code_found:
            hw_found = True

        number_details = extract_number_coordinates(word, tokens_list[i]["coordinates"])
        if (aadhar_found or crif_found) and number_details and is_valid_aadhaar_number(number_details["text"]):
            detected_words.append({
                "text": number_details["text"],
                "coordinates": number_details["coordinates"],
                "type": "number"
            })

        if (aadhar_found or crif_found) and i + 1 < n and is_twelve_digit_number(word + next_word):
            s = word + next_word
            if is_valid_aadhaar_number(s):
                left_coords = tokens_list[i]["coordinates"]
                right_coords = tokens_list[i + 1]["coordinates"]
                coordinates = [
                    (left_coords[0][0], left_coords[0][1]),
                    (right_coords[1][0], right_coords[1][1]),
                    (right_coords[2][0], right_coords[2][1]),
                    (left_coords[3][0], left_coords[3][1])
                ]
                detected_words.append({"text": s, "coordinates": coordinates, "type": "number"})

        if i + 2 < n and (aadhar_found or crif_found):
            if is_four_digit_number(word) and is_four_digit_number(next_word) and is_four_digit_number(next_next_word):
                if (i > 0 and is_four_digit_number(tokens_list[i - 1]["text"])) or \
                   (i + 3 < n and is_four_digit_number(tokens_list[i + 3]["text"])):
                    continue
                aadhaar_number = word + next_word + next_next_word
                if is_valid_aadhaar_number(aadhaar_number):
                    detected_words.append({
                        "text": aadhaar_number,
                        "coordinates": tokens_list[i]["coordinates"],
                        "coordinates_next": tokens_list[i + 1]["coordinates"],
                        "type": "number_split"
                    })

        if "aadhaar" in word.lower() or "aadhar" in word.lower():
            if "card" in next_word.lower() and "no" in next_next_word.lower():
                details = extract_target_coordinates(word, tokens_list[i]["coordinates"], "aadhaar")
                if not details:
                    details = extract_target_coordinates(word, tokens_list[i]["coordinates"], "aadhar")
                if details:
                    detected_words.append({
                        "text": details["text"],
                        "coordinates": details["coordinates"],
                        "type": "app_form_var1"
                    })

        if (cosine_similarity(word, "applicant") >= 0.8 or cosine_similarity(word, "spouse") >= 0.8) and not pmay_found:
            if cosine_similarity(next_word, "aadhar") >= 0.74:
                if "uid" in next_next_word.lower() or "free" in next_next_word.lower():
                    continue
                if i > 0 and "with" in tokens_list[i - 1]["text"].lower():
                    continue
                detected_words.append({
                    "text": next_word,
                    "coordinates": tokens_list[i + 1]["coordinates"],
                    "type": "app_form_var2"
                })

        # PMAY Additional form — aadhaar card applicant
        if "aadhaar" in word.lower() or cosine_similarity(word, "aadhaar") >= 0.8:
            if "card" in word.lower() or levenshtein_score(word, "card") >= 0.7:
                if cosine_similarity(next_next_word, "applicant") >= 0.8:
                    if "aadhaar" in word.lower() or "card" in word.lower():
                        details = extract_target_coordinates(word, tokens_list[i]["coordinates"], "aadhaar card")
                        if details:
                            detected_words.append({
                                "text": details["text"],
                                "coordinates": details["coordinates"],
                                "type": "aadhaarcard_applicant"
                            })
                    else:
                        detected_words.append({
                            "text": word,
                            "coordinates": tokens_list[i]["coordinates"],
                            "type": "aadhaar_card_applicant"
                        })
                    if "aadhaar" in word.lower():
                        details = extract_target_coordinates(word, tokens_list[i]["coordinates"], "aadhaar")
                        if details:
                            detected_words.append({
                                "text": details["text"],
                                "coordinates": details["coordinates"],
                                "type": "aadhaar_card_applicant"
                            })
                    else:
                        detected_words.append({
                            "text": word,
                            "coordinates": tokens_list[i]["coordinates"],
                            "type": "aadhaar_card_applicant"
                        })

        # PMAY Additional form table — aadhaar uid
        if "aadhaar" in word.lower():
            if (
                ("uid" in next_word.lower() or "vid" in next_word.lower())
                and not re.search(r"\b\d{4}\b", next_next_word)
                and "uidai" not in next_word.lower()
            ):
                details = extract_target_coordinates(word, tokens_list[i]["coordinates"], "aadhaar")
                if details:
                    detected_words.append({
                        "text": details["text"],
                        "coordinates": details["coordinates"],
                        "type": "aadhaar_uid"
                    })

        # PMAY Beneficiary Handwritten — aadhar number
        if ("aadhar" in word.lower() or cosine_similarity(word, "aadhar") >= 0.8) and hw_found:
            if "uid" in next_word.lower():
                if i > 0 and "applicant" in tokens_list[i - 1]["text"].lower():
                    continue
                details = extract_target_coordinates(word, tokens_list[i]["coordinates"], "aadhar")
                if details:
                    detected_words.append({
                        "text": details["text"],
                        "coordinates": details["coordinates"],
                        "type": "aadhar_number_pmy_hw"
                    })

        # PMAY Beneficiary Handwritten table
        if cosine_similarity(word, "applicant") >= 0.8 and hw_found:
            if cosine_similarity(next_word, "aadhar") >= 0.8:
                if "uid" in next_next_word.lower():
                    if i > 0 and "with" in tokens_list[i - 1]["text"].lower():
                        detected_words.append({
                            "text": next_word,
                            "coordinates": tokens_list[i + 1]["coordinates"],
                            "type": "aadhar_table_pmy_hw"
                        })

    # Form-lane handwritten recovery: OCR-only pattern rescue for noisy 12-digit strings.
    # IMPORTANT: This path is form-lane-only by flag and does not use YOLO signals.
    if form_lane_only and (aadhar_found or crif_found or hw_found or pmay_found):
        seen_form_hw = set()
        for i in range(n):
            # Check contiguous 1/2/3-token spans to recover merged/split handwritten digits.
            for span in (1, 2, 3):
                end = i + span
                if end > n:
                    break
                combined_text = "".join(tokens_list[k]["text"] for k in range(i, end))
                cleaned = _normalize_ocr_digits(combined_text)
                if len(cleaned) != 12 or not is_valid_aadhaar_number(cleaned):
                    continue

                merged_coords = _merge_token_coordinates(tokens_list, i, end)
                if not merged_coords:
                    continue

                bbox_key = _coords_bbox_key(merged_coords)
                if bbox_key in seen_form_hw:
                    continue

                # Avoid duplicating an existing detection with same region.
                if any(_coords_bbox_key(dw["coordinates"]) == bbox_key for dw in detected_words):
                    seen_form_hw.add(bbox_key)
                    continue

                seen_form_hw.add(bbox_key)
                # Direction hint prevents masking the wrong side when OCR token order is reversed.
                reverse_mask = _token_span_is_right_to_left(tokens_list, i, end)
                detected_words.append({
                    "text": cleaned,
                    "coordinates": merged_coords,
                    "type": "number_form_hw_noise",
                    "reverse": reverse_mask,
                })
                log.info(
                    f"Form lane OCR recovery: masked noisy Aadhaar span tokens={i}:{end} "
                    f"value={cleaned} reverse={reverse_mask}"
                )

    # C3 FIX: Unconditional Verhoeff safety pass
    # If aadhar_found/crif_found is False (keyword corrupted by OCR), still mask valid 12-digit numbers.
    # Form lane only — card lane has YOLO fallback protection.
    if not (aadhar_found or crif_found):
        for i, token in enumerate(tokens_list):
            word = token["text"]
            if is_twelve_digit_number(word):
                cleaned = re.sub(r'[^0-9]', '', word)
                if len(cleaned) == 12 and is_valid_aadhaar_number(cleaned):
                    log.warning(f"C3 FIX: Valid Aadhaar number masked despite missing keyword (OCR corruption?): {cleaned}")
                    detected_words.append({
                        "text": cleaned,
                        "coordinates": token["coordinates"],
                        "type": "number_safety"
                    })

            if i + 1 < len(tokens_list):
                next_word = tokens_list[i + 1]["text"]
                combined = word + next_word
                if is_twelve_digit_number(combined):
                    cleaned = re.sub(r'[^0-9]', '', combined)
                    if len(cleaned) == 12 and is_valid_aadhaar_number(cleaned):
                        log.warning(f"C3 FIX: Valid Aadhaar number masked despite missing keyword (OCR corruption?): {cleaned}")
                        left_coords = token["coordinates"]
                        right_coords = tokens_list[i + 1]["coordinates"]
                        coordinates = [
                            (left_coords[0][0], left_coords[0][1]),
                            (right_coords[1][0], right_coords[1][1]),
                            (right_coords[2][0], right_coords[2][1]),
                            (left_coords[3][0], left_coords[3][1])
                        ]
                        detected_words.append({
                            "text": cleaned,
                            "coordinates": coordinates,
                            "type": "number_safety"
                        })

    log.info(f"find_aadhaar_patterns: {len(detected_words)} patterns found (cersai={cersai_found} crif={crif_found} aadhar={aadhar_found})")
    return detected_words


def mask_ocr_detections(image, detected_words, tokens_list=None):
    """Apply black rectangle masking based on OCR-detected Aadhaar patterns."""
    color = (0, 0, 0)
    for dw in detected_words:
        coords = dw["coordinates"]
        x1 = min(p[0] for p in coords)
        x2 = max(p[0] for p in coords)
        y1 = min(p[1] for p in coords)
        y2 = max(p[1] for p in coords)
        w, h = x2 - x1, y2 - y1
        dtype = dw["type"]
        if dtype == "number_split":
            coords_next = dw.get("coordinates_next", coords)
            x2_next = max(p[0] for p in coords_next)
            y2_next = max(p[1] for p in coords_next)
            cv2.rectangle(image, (int(x1), int(y1)), (int(x2_next), int(y2_next)), color, -1)
        elif dtype == "number_form_hw_noise":
            # Use direction-aware mask region to always cover original first 8 digits.
            reverse = bool(dw.get("reverse", False))
            mask_region = compute_digit_mask_region([x1, y1, x2, y2], reverse=reverse)
            cv2.rectangle(
                image,
                (int(mask_region[0]), int(mask_region[1])),
                (int(mask_region[2]), int(mask_region[3])),
                color,
                -1,
            )
        elif dtype == "number":
            x2_mask = int(x1 + 0.66 * w)
            cv2.rectangle(image, (int(x1), int(y1)), (int(x2_mask), int(y2)), color, -1)
        elif dtype == "app_form_var1":
            x1_mask = int(x2 + 1.65 * w)
            x2_mask = int(x1_mask + 3.9 * w)
            cv2.rectangle(image, (x1_mask, int(y1)), (x2_mask, int(y2)), color, -1)
        elif dtype == "app_form_var2":
            x1_mask = int(x2 + 0.65 * w)
            x2_mask = int(x1_mask + 3.75 * w)
            cv2.rectangle(image, (x1_mask, int(y1)), (x2_mask, int(y2)), color, -1)
        elif dtype == "aadhaar_card_applicant":
            x1_mask = int(x2 + 1.9 * w)
            x2_mask = int(x1_mask + 2.95 * w)
            y1_mask = int(y1 - 0.15 * h)
            y2_mask = int(y1_mask + 2.20 * h)
            cv2.rectangle(image, (x1_mask, y1_mask), (x2_mask, y2_mask), color, -1)
        elif dtype == "aadhaarcard_applicant":
            x1_mask = int(x2 + 1.25 * w)
            x2_mask = int(x1_mask + 2.85 * w)
            y2_mask = int(y1 + 2.25 * h)
            cv2.rectangle(image, (x1_mask, int(y1)), (x2_mask, y2_mask), color, -1)
        elif dtype == "aadhar_number_pmy_hw":
            x1_mask = int(x2 + w)
            x2_mask = int(x1_mask + 2.5 * w)
            cv2.rectangle(image, (x1_mask, int(y1)), (x2_mask, int(y2)), color, -1)
        elif dtype == "aadhaar_uid":
            x1_mask = int(x1 - 1.08 * w)
            x2_mask = int(x1_mask + 2.5 * w)
            y1_mask = int(y2 + 1.25 * h)
            y2_mask = int(y1_mask + 7.92 * h)
            w_mask = int(1.5 * (x2_mask - x1_mask))
            if tokens_list is not None:
                y2_mask = int(uid_table_masking_coordinates(x1_mask, x1_mask + w_mask, y1_mask, y2_mask, tokens_list))
            if y2_mask - y1_mask > 5:
                cv2.rectangle(image, (x1_mask, y1_mask), (x2_mask, y2_mask), color, -1)
        elif dtype == "aadhar_table_pmy_hw":
            x1_mask = int(x1)
            x2_mask = int(x1_mask + 2.5 * w)
            y1_mask = int(y2)
            y2_mask = int(y1_mask + 4 * h)
            w_mask = int(1.5 * (x2_mask - x1_mask))
            if tokens_list is not None:
                y2_mask = int(uid_table_masking_coordinates(x1_mask, x2_mask + w_mask, y1_mask, y2_mask, tokens_list))
            if abs(y2_mask - y1_mask) > 5:
                cv2.rectangle(image, (x1_mask, y1_mask), (x2_mask, y2_mask), color, -1)
    return image
