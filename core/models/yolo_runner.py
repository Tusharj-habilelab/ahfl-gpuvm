"""
yolo_runner.py — YOLO model management for AHFL-Masking 1.1

Centralized singleton-based YOLO model loader and inference wrapper.
Prevents duplicate model loads and provides consistent error handling.
"""

import logging
import os
import threading
import torch
from typing import Optional, Tuple
from functools import lru_cache

from ultralytics import YOLO
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed; rely on environment variables set directly

log = logging.getLogger(__name__)

# Import from config — single source of truth so all services use the same default.
from core.config import GPU_ENABLED as _GPU_ENABLED
_CUDA_AVAILABLE = torch.cuda.is_available()
_DEVICE = "cuda" if (_CUDA_AVAILABLE and _GPU_ENABLED) else "cpu"

# Module-level singletons (lazy-loaded)
_yolo_main: Optional[YOLO] = None
_yolo_best: Optional[YOLO] = None
_yolo_main_lock = threading.Lock()
_yolo_best_lock = threading.Lock()


class YOLORunner:
    """
    Wrapper class for YOLO model management.
    Can be instantiated per-service or used as module-level singletons.
    """

    def __init__(
        self,
        model_main_path: str = "models/main.pt",
        model_best_path: str = "models/best.pt",
    ):
        self.model_main_path = model_main_path
        self.model_best_path = model_best_path
        self._yolo_main: Optional[YOLO] = None
        self._yolo_best: Optional[YOLO] = None

    def get_main(self) -> YOLO:
        """Load and return the main YOLO model (lazy)."""
        if self._yolo_main is None:
            try:
                log.info(f"Loading YOLO main from {self.model_main_path}...")
                self._yolo_main = YOLO(self.model_main_path).to(_DEVICE)
                log.info(f"✓ YOLO main loaded on {_DEVICE}")
            except Exception as e:
                log.error(f"Failed to load YOLO main: {e}")
                raise RuntimeError(f"Cannot load YOLO main: {e}") from e
        return self._yolo_main

    def get_best(self) -> YOLO:
        """Load and return the best YOLO model (lazy)."""
        if self._yolo_best is None:
            try:
                log.info(f"Loading YOLO best from {self.model_best_path}...")
                self._yolo_best = YOLO(self.model_best_path).to(_DEVICE)
                log.info(f"✓ YOLO best loaded on {_DEVICE}")
            except Exception as e:
                log.error(f"Failed to load YOLO best: {e}")
                raise RuntimeError(f"Cannot load YOLO best: {e}") from e
        return self._yolo_best

    def run_inference(self, image_path: str) -> Tuple[object, object]:
        """
        Run inference with both models on an image.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (main_results, best_results)
        """
        try:
            main_results = self.get_main()(image_path)[0]
            best_results = self.get_best()(image_path)[0]
            return main_results, best_results
        except Exception as e:
            log.error(f"Inference failed on {image_path}: {e}")
            raise


def get_yolo_main() -> YOLO:
    """
    Module-level singleton getter for main YOLO model.

    Usage:
        from core.models import get_yolo_main
        yolo = get_yolo_main()
        results = yolo(image_path)[0]
    """
    global _yolo_main
    if _yolo_main is None:
        with _yolo_main_lock:
            if _yolo_main is None:
                model_path = os.environ.get("MODEL_MAIN", "models/main.pt")
                try:
                    log.info(f"Loading YOLO main from {model_path}...")
                    _yolo_main = YOLO(model_path).to(_DEVICE)
                    log.info(f"✓ YOLO main loaded on {_DEVICE}")
                except Exception as e:
                    log.error(f"Failed to load YOLO main: {e}")
                    raise RuntimeError(f"Cannot load YOLO main: {e}") from e
    return _yolo_main


def get_yolo_best() -> YOLO:
    """
    Module-level singleton getter for best YOLO model.

    Usage:
        from core.models import get_yolo_best
        yolo = get_yolo_best()
        results = yolo(image_path)[0]
    """
    global _yolo_best
    if _yolo_best is None:
        with _yolo_best_lock:
            if _yolo_best is None:
                model_path = os.environ.get("MODEL_BEST", "models/best.pt")
                try:
                    log.info(f"Loading YOLO best from {model_path}...")
                    _yolo_best = YOLO(model_path).to(_DEVICE)
                    log.info(f"✓ YOLO best loaded on {_DEVICE}")
                except Exception as e:
                    log.error(f"Failed to load YOLO best: {e}")
                    raise RuntimeError(f"Cannot load YOLO best: {e}") from e
    return _yolo_best


def reset_models() -> None:
    """Reset module-level singletons (useful for testing)."""
    global _yolo_main, _yolo_best
    _yolo_main = None
    _yolo_best = None
    log.info("YOLO models reset")
