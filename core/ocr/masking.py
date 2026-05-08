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
    box: list, mask_digits: int = 8, total_digits: int = 12
) -> tuple:
    """
    Compute the sub-region covering the first N digits of a number bbox.

    FALLBACK masking when OCR cannot read individual digit positions.
    Masks a proportional fraction (8/12 = 0.667) of the bounding box.

    Handles both horizontal and vertical number orientations:
      - Horizontal: mask left portion (width-based)
      - Vertical: mask top portion (height-based)

    Args:
        box: [x1, y1, x2, y2] bounding box of the full number.
        mask_digits: Number of digits to mask (default 8).
        total_digits: Total digits in number (default 12).

    Returns:
        (x1, y1, x2_mask, y2_mask) — the region to black out.
    """
    x1, y1, x2, y2 = [int(c) for c in box]
    w = x2 - x1
    h = y2 - y1
    fraction = mask_digits / total_digits

    if w > h:
        # Horizontal number: mask left portion
        x2_mask = int(x1 + fraction * w)
        return (x1, y1, x2_mask, y2)
    else:
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


def merge_detections(detections1, detections2, iou_threshold=0.5):
    """
    Merge detections from two YOLO models, removing duplicates via IoU.
    Each detection: {"box": [x1,y1,x2,y2], "label": str, "conf": float, "model": str}
    """
    merged = [dict(d) for d in detections1]
    for det2 in detections2:
        is_duplicate = False
        for det1 in merged:
            if calculate_iou(det1["box"], det2["box"]) > iou_threshold:
                if det2["conf"] > det1["conf"]:
                    det1.update(det2)
                is_duplicate = True
                break
        if not is_duplicate:
            merged.append(det2)
    return merged


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
    return 'x' in text.lower() or 'y' in text.lower() or 'k' in text.lower()


def _ocr_verify_and_mask_number(image, box, label, ocr, stats=None):
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
            return image, False

        texts, _, _ = get_texts_and_boxes(adapted)
        all_text = ' '.join(texts)

        # Extract digits only
        digits = re.sub(r'[^0-9]', '', all_text)

        if len(digits) != 12 or not is_valid_aadhaar_number(digits):
            return image, False

        # Valid 12-digit Aadhaar found via OCR — mask first 8 digits
        # Use proportional masking: 8/12 of the bbox width/height
        color = (0, 0, 0)
        mask_region = compute_digit_mask_region(box, mask_digits=8, total_digits=12)
        cv2.rectangle(
            image,
            (mask_region[0], mask_region[1]),
            (mask_region[2], mask_region[3]),
            color, -1
        )

        if stats is not None:
            stats["ocr_verified_masks"] = stats.get("ocr_verified_masks", 0) + 1

        return image, True

    except Exception:
        return image, False


def mask_yolo_detections(image, merged_detections, debug=False, stats=None, ocr=None, aadhaar_boxes=None):
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
        if "qr" in label and conf > 0.3:
            report_data["is_qr"] += 1
            if "masked" not in label:
                # Spatial check: only mask QR inside Aadhaar card bbox
                if aadhaar_boxes and is_inside_aadhaar_by_area(det["box"], aadhaar_boxes):
                    cv2.rectangle(image, (x1, y1), (x2, y2), color, -1)
                    report_data["is_qr_masked"] += 1
                elif not aadhaar_boxes:
                    log.debug(f"QR skipped (no Aadhaar bbox): box=[{x1},{y1},{x2},{y2}]")
                else:
                    log.debug(f"QR skipped (outside Aadhaar bbox): box=[{x1},{y1},{x2},{y2}]")
        elif "number" in label and conf > 0.3:
            report_data["is_number"] += 1
            if "masked" not in label and "xx" not in label:
                try:
                    already_masked = check_image_text(image, det["box"], det["label"], stats=stats, ocr=ocr)
                except Exception:
                    already_masked = False
                if not already_masked:
                    # Primary: OCR-verified digit masking
                    image, ocr_success = _ocr_verify_and_mask_number(
                        image, det["box"], det["label"], ocr, stats=stats
                    )
                    if not ocr_success:
                        # Fallback: proportional width masking (8/12)
                        mask_region = compute_digit_mask_region(det["box"])
                        cv2.rectangle(
                            image,
                            (mask_region[0], mask_region[1]),
                            (mask_region[2], mask_region[3]),
                            color, -1
                        )
                    report_data["is_number_masked"] += 1
                else:
                    report_data["is_xx"] += 1
        elif "xx" in label:
            report_data["is_xx"] += 1
    log.info(
        f"mask_yolo: number={report_data['is_number']} masked={report_data['is_number_masked']} "
        f"qr={report_data['is_qr']} qr_masked={report_data['is_qr_masked']} xx={report_data['is_xx']}"
    )
    return image, report_data


# ============================================================
# OCR-Based Masking (Pattern matching on extracted text)
# ============================================================

def find_aadhaar_patterns(tokens_list):
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
