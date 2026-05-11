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
    # NOTE: Keep matrix construction centralized so inverse mapping can reuse it.
    M, new_w, new_h = _build_rotation_matrix(image.shape[1], image.shape[0], angle)

    return cv2.warpAffine(
        image,
        M,
        (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def _build_rotation_matrix(width: int, height: int, angle: float):
    """Build forward affine matrix for original->rotated canvas and return new bounds."""
    w, h = int(width), int(height)
    cx, cy = w / 2, h / 2

    M = cv2.getRotationMatrix2D((cx, cy), -angle, 1.0)

    cos_a = abs(M[0, 0])
    sin_a = abs(M[0, 1])
    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)

    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2

    return M, new_w, new_h


def rotate_back_to_original_space(
    rotated_image: np.ndarray,
    angle: int,
    original_shape: Tuple[int, int],
) -> np.ndarray:
    """
    Rotate winner-angle image back to original orientation for any angle.

    Args:
        rotated_image: Image currently in winner-angle orientation.
        angle: Winner angle used for forward rotation.
        original_shape: Original image shape as (height, width).
    """
    if angle == 0:
        return rotated_image

    orig_h, orig_w = int(original_shape[0]), int(original_shape[1])

    # Fast-path for cardinal angles keeps existing behavior and avoids interpolation drift.
    if angle in (90, 180, 270):
        inverse_angle = {90: 270, 180: 180, 270: 90}[int(angle)]
        return rotate_image(rotated_image, inverse_angle)

    # NOTE: For non-cardinal angles (45/135/225/315), use inverse affine transform.
    fwd_M, _, _ = _build_rotation_matrix(orig_w, orig_h, float(angle))
    inv_M = cv2.invertAffineTransform(fwd_M)

    return cv2.warpAffine(
        rotated_image,
        inv_M,
        (orig_w, orig_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def _rotate_by_angle(image: np.ndarray, angle: int) -> np.ndarray:
    if angle in (0, 90, 180, 270):
        return rotate_image(image, angle)
    return rotate_image_affine(image, angle)


def find_best_orientation(
    image: np.ndarray,
    score_fn: Callable[[np.ndarray], Tuple[float, Dict[str, Any]]],
) -> Tuple[np.ndarray, int, Dict[str, Any]]:
    """
    Try ALL candidate angles, compute full composite score for each,
    then pick the angle with the highest score.

    No early exits — every angle is evaluated so the best orientation
    is selected based on complete evidence (Aadhaar + number + QR).

    Returns:
        (best_rotated_image, best_angle, gate_result)
    """
    score_0, data_0 = score_fn(image)

    if not ORIENTATION_ENABLED:
        return image, 0, data_0

    # Cache: angle -> (rotated_image, score, gate_data)
    scored_cache: Dict[int, Tuple[np.ndarray, float, Dict[str, Any]]] = {
        0: (image, score_0, data_0)
    }

    # Use doc orientation hint to pre-compute that angle (avoids redundant rotation later)
    hint_angle = _get_doc_orientation_hint(image)
    log.info(f"Orientation: doc hint={hint_angle}°")
    if hint_angle != 0 and hint_angle in ORIENTATION_ANGLES:
        hint_rotated = _rotate_by_angle(image, hint_angle)
        hint_score, hint_data = score_fn(hint_rotated)
        scored_cache[hint_angle] = (hint_rotated, hint_score, hint_data)

    # Evaluate all angles (using cache for already-scored ones)
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

        log.info(
            f"Orientation: angle={angle}° score={score:.4f} "
            f"aadhaar_conf={data.get('max_aadhaar_conf', 0):.3f} "
            f"number_conf={data.get('best_number_conf', 0):.3f} "
            f"qr_conf={data.get('best_qr_conf', 0):.3f}"
        )

        if score > best_score:
            best_score = score
            best_angle = angle
            best_image = rotated
            best_data = data

    log.info(
        f"Orientation: selected {best_angle}° "
        f"(score={best_score:.4f}, tried={len(ORIENTATION_ANGLES)} angles)"
    )
    return best_image, best_angle, best_data
