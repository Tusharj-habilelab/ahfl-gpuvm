"""
spatial.py — Spatial containment logic for AHFL-Masking 1.1

Determines whether detected elements (QR codes, numbers) are spatially
inside an Aadhaar card bounding box. Used to prevent masking QR codes
from other documents (PAN, voter ID, etc.) that appear on the same page.

Key function:
  is_inside_aadhaar_by_area(qr_box, aadhaar_boxes, threshold=0.5)
    → True if >= threshold of QR area overlaps ANY Aadhaar bbox.
"""

from typing import List
import logging

log = logging.getLogger(__name__)


def compute_intersection_area(
    box1: List[float], box2: List[float]
) -> float:
    """
    Compute the intersection area of two axis-aligned bounding boxes.

    Args:
        box1: [x1, y1, x2, y2]
        box2: [x1, y1, x2, y2]

    Returns:
        Intersection area (0.0 if no overlap).
    """
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    if x2 <= x1 or y2 <= y1:
        return 0.0

    return (x2 - x1) * (y2 - y1)


def is_inside_aadhaar_by_area(
    qr_box: List[float],
    aadhaar_boxes: List[List[float]],
    threshold: float = 0.5,
) -> bool:
    """
    Check if a QR code is spatially inside any Aadhaar card bounding box.

    A QR is considered "inside" if >= threshold of its area overlaps
    at least one Aadhaar bbox.

    Args:
        qr_box: [x1, y1, x2, y2] of the QR detection.
        aadhaar_boxes: List of [x1, y1, x2, y2] for detected Aadhaar cards.
        threshold: Minimum overlap fraction (default 0.5 = 50%).

    Returns:
        True if QR is inside an Aadhaar card, False otherwise.
    """
    qr_area = (qr_box[2] - qr_box[0]) * (qr_box[3] - qr_box[1])
    if qr_area <= 0:
        return False

    for aadhaar_box in aadhaar_boxes:
        overlap = compute_intersection_area(qr_box, aadhaar_box)
        if overlap / qr_area >= threshold:
            return True

    return False


def find_aadhaar_card_boxes(detections: List[dict]) -> List[List[float]]:
    """
    Extract Aadhaar card bounding boxes from merged detections.

    Looks for detections with label "aadhaar" (case-insensitive).

    Args:
        detections: List of detection dicts with "box" and "label" keys.

    Returns:
        List of [x1, y1, x2, y2] boxes for Aadhaar card detections.
    """
    return [
        d["box"] for d in detections
        if d.get("label", "").lower() == "aadhaar"
    ]


def find_qr_boxes(detections: List[dict]) -> List[dict]:
    """
    Extract QR code detections from merged detections.

    Looks for labels containing "qr" (case-insensitive), excluding
    already-masked QR codes ("is_qr_masked").

    Args:
        detections: List of detection dicts with "box" and "label" keys.

    Returns:
        List of detection dicts for unmasked QR codes.
    """
    return [
        d for d in detections
        if "qr" in d.get("label", "").lower()
        and "masked" not in d.get("label", "").lower()
    ]


def filter_dets_inside_box(
    detections: List[dict],
    container_box: List[float],
    threshold: float = 0.3,
) -> List[dict]:
    """
    Filter detections to those inside a container bounding box.

    A detection is "inside" if >= threshold of its area overlaps the container.

    Args:
        detections: List of detection dicts with "box" key.
        container_box: [x1, y1, x2, y2] of the container region.
        threshold: Minimum overlap fraction (default 0.3).

    Returns:
        List of detection dicts that are inside the container.
    """
    inside = []
    for det in detections:
        box = det["box"]
        det_area = (box[2] - box[0]) * (box[3] - box[1])
        if det_area <= 0:
            continue
        overlap = compute_intersection_area(box, container_box)
        if overlap / det_area >= threshold:
            inside.append(det)
    return inside


def map_dets_to_crop(
    detections: List[dict],
    crop_box: List[float],
) -> List[dict]:
    """
    Remap detection coordinates from full-image space to crop-relative space.

    Subtracts crop origin (x1, y1) and clamps to crop bounds.

    Args:
        detections: List of detection dicts with "box" in full-image coords.
        crop_box: [x1, y1, x2, y2] of the crop region in full-image coords.

    Returns:
        New list of detection dicts with "box" in crop-relative coords.
    """
    cx1, cy1, cx2, cy2 = crop_box
    cw = cx2 - cx1
    ch = cy2 - cy1
    mapped = []
    for det in detections:
        bx1, by1, bx2, by2 = det["box"]
        nx1 = max(0, bx1 - cx1)
        ny1 = max(0, by1 - cy1)
        nx2 = min(cw, bx2 - cx1)
        ny2 = min(ch, by2 - cy1)
        if nx2 > nx1 and ny2 > ny1:
            mapped.append({**det, "box": [nx1, ny1, nx2, ny2]})
    return mapped


def map_crop_dets_to_full(
    detections: List[dict],
    crop_box: List[float],
) -> List[dict]:
    """
    Remap detection coordinates from crop-relative space to full-image space.

    Adds crop origin (x1, y1) offset.

    Args:
        detections: List of detection dicts with "box" in crop-relative coords.
        crop_box: [x1, y1, x2, y2] of the crop region in full-image coords.

    Returns:
        New list of detection dicts with "box" in full-image coords.
    """
    cx1, cy1 = crop_box[0], crop_box[1]
    return [
        {**det, "box": [
            det["box"][0] + cx1,
            det["box"][1] + cy1,
            det["box"][2] + cx1,
            det["box"][3] + cy1,
        ]}
        for det in detections
    ]
