"""
angle_detector.py — Orientation detection via rotation + full gate scoring.
"""

import logging
from typing import Any, Callable, Dict, Tuple

import cv2
import numpy as np

from core.config import (
    ORIENTATION_ANGLES,
    ORIENTATION_ENABLED,
    ORIENTATION_STRONG_THRESHOLD,
    ORIENTATION_TARGET_THRESHOLD,
)
from core.ocr.paddle import get_doc_orientation_model

log = logging.getLogger(__name__)


def _get_doc_orientation_hint(image: np.ndarray) -> int:
    """Predict coarse rotation hint (0/90/180/270). Returns 0 on failure."""
    try:
        model = get_doc_orientation_model()
        result = model.predict(image)[0]
        label = result.json["res"]["label_names"][0]
        return int(label)
    except Exception as e:
        log.debug(f"doc_orientation hint failed: {e}")
        return 0


def rotate_image(image: np.ndarray, angle: int) -> np.ndarray:
    """Rotate image by cardinal angle."""
    if angle == 0:
        return image
    if angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def rotate_image_affine(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate image by arbitrary angle using affine transform."""
    h, w = image.shape[:2]
    cx, cy = w / 2, h / 2

    M = cv2.getRotationMatrix2D((cx, cy), -angle, 1.0)

    cos_a = abs(M[0, 0])
    sin_a = abs(M[0, 1])
    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)

    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2

    return cv2.warpAffine(
        image,
        M,
        (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def _rotate_by_angle(image: np.ndarray, angle: int) -> np.ndarray:
    if angle in (0, 90, 180, 270):
        return rotate_image(image, angle)
    return rotate_image_affine(image, angle)


def _check_composite_early_exit(gate_result: Dict[str, Any]) -> bool:
    """Composite early exit: strong Aadhaar + strong number/QR evidence."""
    aadhaar_conf = gate_result.get("max_aadhaar_conf", 0.0)
    number_conf = gate_result.get("best_number_conf", 0.0)
    qr_conf = gate_result.get("best_qr_conf", 0.0)

    strong_aadhaar = aadhaar_conf >= ORIENTATION_STRONG_THRESHOLD
    strong_target = (
        number_conf >= ORIENTATION_TARGET_THRESHOLD
        or qr_conf >= ORIENTATION_TARGET_THRESHOLD
    )
    return strong_aadhaar and strong_target


def find_best_orientation(
    image: np.ndarray,
    score_fn: Callable[[np.ndarray], Tuple[float, Dict[str, Any]]],
) -> Tuple[np.ndarray, int, Dict[str, Any]]:
    """
    Try candidate angles and pick the best full-gate score.

    Returns:
        (best_rotated_image, best_angle, gate_result)
    """
    score_0, data_0 = score_fn(image)

    if not ORIENTATION_ENABLED:
        return image, 0, data_0

    if _check_composite_early_exit(data_0):
        log.debug(
            "Orientation: early exit at 0° "
            f"(aadhaar={data_0.get('max_aadhaar_conf', 0):.3f}, "
            f"number={data_0.get('best_number_conf', 0):.3f}, "
            f"qr={data_0.get('best_qr_conf', 0):.3f})"
        )
        return image, 0, data_0

    scored_cache: Dict[int, Tuple[np.ndarray, float, Dict[str, Any]]] = {0: (image, score_0, data_0)}

    hint_angle = _get_doc_orientation_hint(image)
    if hint_angle != 0 and hint_angle in ORIENTATION_ANGLES:
        hint_rotated = _rotate_by_angle(image, hint_angle)
        hint_score, hint_data = score_fn(hint_rotated)
        scored_cache[hint_angle] = (hint_rotated, hint_score, hint_data)
        if _check_composite_early_exit(hint_data):
            log.debug(
                f"Orientation: doc hint early exit at {hint_angle}° "
                f"(aadhaar={hint_data.get('max_aadhaar_conf', 0):.3f}, "
                f"number={hint_data.get('best_number_conf', 0):.3f}, "
                f"qr={hint_data.get('best_qr_conf', 0):.3f})"
            )
            return hint_rotated, hint_angle, hint_data

    best_angle = 0
    best_score = score_0
    best_image = image
    best_data = data_0

    for angle in ORIENTATION_ANGLES:
        if angle in scored_cache:
            rotated, score, data = scored_cache[angle]
        else:
            rotated = _rotate_by_angle(image, angle)
            score, data = score_fn(rotated)

        if _check_composite_early_exit(data):
            log.debug(
                f"Orientation: early exit at {angle}° "
                f"(aadhaar={data.get('max_aadhaar_conf', 0):.3f}, "
                f"number={data.get('best_number_conf', 0):.3f}, "
                f"qr={data.get('best_qr_conf', 0):.3f})"
            )
            return rotated, angle, data

        if score > best_score:
            best_score = score
            best_angle = angle
            best_image = rotated
            best_data = data

    log.debug(
        f"Orientation: selected {best_angle}° "
        f"(score={best_score:.4f}, tried={len(ORIENTATION_ANGLES)} angles)"
    )
    return best_image, best_angle, best_data
