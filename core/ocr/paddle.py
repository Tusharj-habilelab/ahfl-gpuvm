"""
Shared PaddleOCR helpers for AHFL-Masking 1.1.

Keeps PaddleOCR initialization and image preparation consistent across
services so we do not end up debugging different OCR behaviors in each path.
"""

import os
import logging
import threading
from pathlib import Path

import cv2
from typing import Optional
from paddleocr import PaddleOCR, DocImgOrientationClassification
from core.config import PADDLE_MODEL_DIR, PADDLE_OCR_MAX_SIDE, ROUTER_OCR_LITE_MAX_SIDE, ROUTER_OCR_LITE_MAX_TOKENS

log = logging.getLogger(__name__)


def _log_paddle_cache_resolution() -> None:
    """Log resolved Paddle cache/model path details (including symlink targets)."""
    # NOTE: Keep this explicit because cache-path confusion caused debugging overhead before.
    env_model_dir = str(PADDLE_MODEL_DIR)
    expanded_model_dir = str(Path(env_model_dir).expanduser())
    default_cache_dir = Path("~/.paddlex").expanduser()
    cache_symlink_target = ""
    if default_cache_dir.is_symlink():
        try:
            cache_symlink_target = str(default_cache_dir.resolve())
        except Exception:
            cache_symlink_target = "<unresolved>"

    log.info(
        "PaddleOCR cache/model paths: "
        f"PADDLE_MODEL_DIR={env_model_dir} "
        f"expanded={expanded_model_dir} "
        f"default_cache={default_cache_dir} "
        f"default_cache_symlink={default_cache_dir.is_symlink()} "
        f"default_cache_target={cache_symlink_target}"
    )


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_paddle_device() -> str:
    """Return paddle device string: env override > GPU auto-detect > cpu."""
    override = os.getenv("PADDLE_DEVICE")
    if override:
        return override
    try:
        import paddle
        if paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            return "gpu:0"
    except Exception:
        pass
    return "cpu"


def create_paddle_ocr() -> PaddleOCR:
    """
    Build a PaddleOCR instance for Aadhaar text extraction (PaddleOCR 3.4.0+).
    Models cached to /root/.paddlex/official_models/ (volume-mounted, downloaded once on first run).
    """
    device = _get_paddle_device()
    # NOTE: Log cache/model resolution before initialization to diagnose model-source/path issues.
    _log_paddle_cache_resolution()
    log.info(f"PaddleOCR: initializing (lang=en, use_textline_orientation=True, device={device})")
    # NOTE: Paddle downloads internally on first run; this log marks potential cold start.
    log.info("PaddleOCR: init start (if cache missing, model download may occur)")
    ocr = PaddleOCR(
        lang="en",
        use_textline_orientation=True,
        device=device,
    )
    log.info("PaddleOCR: initialization complete")
    return ocr


_doc_ori_model = None
_doc_ori_lock = threading.Lock()


def get_doc_orientation_model() -> DocImgOrientationClassification:
    """
    Lazy-load shared DocImgOrientationClassification instance.

    Model: PP-LCNet_x1_0_doc_ori (7MB, ~3ms inference).
    Predicts whole-document rotation: 0 / 90 / 180 / 270 degrees.
    Cached to /root/.paddlex/official_models/ (auto-downloaded once, reused offline).
    """
    global _doc_ori_model
    if _doc_ori_model is None:
        with _doc_ori_lock:
            if _doc_ori_model is None:
                device = _get_paddle_device()
                log.info(f"DocOrientationModel: initializing (device={device})")
                _doc_ori_model = DocImgOrientationClassification(
                    device=device,
                )
                log.info("DocOrientationModel: ready")
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


def run_ocr_lite_for_routing(image, max_tokens: Optional[int] = None, ocr=None):
    """
    Lightweight OCR for document routing only (not masking).

    Resizes image aggressively and extracts only top N text tokens.
    No coordinate information returned - pure text for keyword matching.

    Args:
        image: BGR numpy array
        max_tokens: Maximum number of tokens to extract
        ocr: Optional PaddleOCR singleton. If provided, used directly.
             Falls back to pytesseract if None.

    Returns:
        List of text tokens (strings), or empty list on failure
    """
    if max_tokens is None:
        max_tokens = ROUTER_OCR_LITE_MAX_TOKENS

    try:
        height, width = image.shape[:2]
        max_side = ROUTER_OCR_LITE_MAX_SIDE
        if max(height, width) > max_side:
            scale = max_side / max(height, width)
            new_w = max(1, int(width * scale))
            new_h = max(1, int(height * scale))
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        if ocr is not None:
            try:
                from core.ocr.ocr_adapter import adapt_paddle_result, get_texts_and_boxes
                results = ocr.ocr(image)
                if results and results[0]:
                    adapted = adapt_paddle_result(results)
                    texts, _, _ = get_texts_and_boxes(adapted)
                    # NOTE: INFO level by request so lane-routing evidence is visible in normal runs.
                    log.info(f"run_ocr_lite_for_routing: tokens={len(texts)}")
                    return texts[:max_tokens]
                return []
            except Exception as e:
                log.warning(f"run_ocr_lite_for_routing PaddleOCR failed: {e} — falling back to pytesseract")

        try:
            import pytesseract
            text = pytesseract.image_to_string(image)
            if text:
                tokens = [t.strip() for t in text.split() if t.strip()]
                return tokens[:max_tokens]
        except ImportError:
            log.warning("run_ocr_lite_for_routing: pytesseract not available and no ocr passed — returning empty tokens")
            return []
        except Exception as e:
            log.warning(f"run_ocr_lite_for_routing pytesseract failed: {e}")
            return []

    except Exception as e:
        log.error(f"run_ocr_lite_for_routing failed: {e}")
        return []
