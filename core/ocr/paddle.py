"""
Shared PaddleOCR helpers for AHFL-Masking 1.1.

Keeps PaddleOCR initialization and image preparation consistent across
services so we do not end up debugging different OCR behaviors in each path.
"""

import os
import threading

import cv2
from typing import Optional
from paddleocr import PaddleOCR, DocImgOrientationClassification
from core.config import PADDLE_OCR_MAX_SIDE, ROUTER_OCR_LITE_MAX_SIDE, ROUTER_OCR_LITE_MAX_TOKENS


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def create_paddle_ocr() -> PaddleOCR:
    """
    Build a PaddleOCR instance for Aadhaar text extraction (PaddleOCR 3.4.0+).
    Models are auto-downloaded to /root/.paddlex on first call and cached permanently.
    GPU mode imports from core.config — single source of truth for GPU_ENABLED default.
    """
    # Import here to avoid circular imports (paddle.py is imported by core/pipeline.py)
    from core.config import GPU_ENABLED as _use_gpu, PADDLE_MODEL_DIR as _model_dir
    return PaddleOCR(
        lang="en",
        use_textline_orientation=True,
        device="gpu:0" if _use_gpu else "cpu",
        det_model_dir=os.path.join(_model_dir, "det"),
        rec_model_dir=os.path.join(_model_dir, "rec"),
        cls_model_dir=os.path.join(_model_dir, "cls"),
    )


_doc_ori_model = None
_doc_ori_lock = threading.Lock()


def get_doc_orientation_model() -> DocImgOrientationClassification:
    """
    Lazy-load shared DocImgOrientationClassification instance.

    Model: PP-LCNet_x1_0_doc_ori (7MB, ~3ms CPU inference).
    Predicts whole-document rotation: 0 / 90 / 180 / 270 degrees.
    Auto-downloaded to /root/.paddlex on first call and cached permanently.
    """
    global _doc_ori_model
    if _doc_ori_model is None:
        with _doc_ori_lock:
            if _doc_ori_model is None:
                _doc_ori_model = DocImgOrientationClassification()
    return _doc_ori_model


def resize_image_for_ocr(image, max_side: Optional[int] = None):
    """
    Resize large images before OCR to keep CPU inference bounded.

    Returns:
        resized_image, scale_to_original
    """
    if max_side is None:
        max_side = PADDLE_OCR_MAX_SIDE

    height, width = image.shape[:2]
    longest_side = max(height, width)
    if longest_side <= max_side:
        return image, 1.0

    scale = max_side / float(longest_side)
    new_w = max(1, int(width * scale))
    new_h = max(1, int(height * scale))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, 1.0 / scale


def scale_adapted_ocr_results(adapted_results, scale_to_original: float):
    """Scale OCR polygons back to the original image coordinate space."""
    if scale_to_original == 1.0:
        return adapted_results

    scaled = []
    for bbox, text, confidence in adapted_results:
        scaled_bbox = [
            (int(x * scale_to_original), int(y * scale_to_original))
            for x, y in bbox
        ]
        scaled.append((scaled_bbox, text, confidence))
    return scaled


def run_ocr_lite_for_routing(image, max_tokens: Optional[int] = None):
    """
    Lightweight OCR for document routing only (not masking).
    
    Resizes image aggressively and extracts only top N text tokens.
    No coordinate information returned - pure text for keyword matching.
    
    Args:
        image: BGR numpy array
        max_tokens: Maximum number of tokens to extract
    
    Returns:
        List of text tokens (strings), or empty list on failure
    """
    import logging
    log = logging.getLogger(__name__)
    if max_tokens is None:
        max_tokens = ROUTER_OCR_LITE_MAX_TOKENS
    
    try:
        # Aggressive resize for speed - routing doesn't need high resolution
        height, width = image.shape[:2]
        max_side = ROUTER_OCR_LITE_MAX_SIDE
        if max(height, width) > max_side:
            scale = max_side / max(height, width)
            new_w = max(1, int(width * scale))
            new_h = max(1, int(height * scale))
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Use shared PaddleOCR instance from create_paddle_ocr()
        # We can't create a separate instance here as it would waste GPU memory
        # Instead we'll use a very simple pytesseract fallback for routing
        # This keeps the router lightweight and independent
        
        # Simple pytesseract extraction for routing only
        try:
            import pytesseract
            text = pytesseract.image_to_string(image)
            if text:
                # Split into tokens, filter empty, limit to max_tokens
                tokens = [t.strip() for t in text.split() if t.strip()]
                return tokens[:max_tokens]
        except ImportError:
            log.warning("pytesseract not available for OCR-lite routing, using empty tokens")
            return []
        except Exception as e:
            log.warning(f"OCR-lite routing failed: {e}")
            return []
    
    except Exception as e:
        log.error(f"run_ocr_lite_for_routing failed: {e}")
        return []
