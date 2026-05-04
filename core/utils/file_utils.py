"""
file_utils.py — File and document handling utilities for AHFL-Masking 1.1

Consolidated helpers for PDF conversion, image processing, and file validation.
"""

import os
import logging
import tempfile
from pathlib import Path
from typing import List, Tuple

from core.config import MAX_FILE_SIZE as _MAX_FILE_SIZE_BYTES

log = logging.getLogger(__name__)

_MAX_FILE_SIZE_MB = _MAX_FILE_SIZE_BYTES // (1024 * 1024)

# Supported file types
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def is_supported_file(file_path: str) -> bool:
    """Check if a file extension is in the supported list."""
    ext = Path(file_path).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS


def pdf_to_images(pdf_path: str, dpi: int = 200) -> Tuple[List[str], tempfile.TemporaryDirectory]:
    """
    Convert a PDF file to a list of image paths.

    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for conversion (default 200)

    Returns:
        Tuple of (image_paths, tmp_dir_handle) — call tmp_dir_handle.cleanup() when done.
    """
    try:
        from pdf2image import convert_from_path

        pages = convert_from_path(pdf_path, dpi=dpi)
        image_paths = []

        tmp_dir = tempfile.TemporaryDirectory(prefix="ahfl_pdf_")
        for i, page in enumerate(pages):
            img_path = os.path.join(tmp_dir.name, f"page_{i:04d}.jpg")
            page.convert('RGB').save(img_path, "JPEG")  # Force RGB (3 channels for YOLO)
            image_paths.append(img_path)
            del page

        log.info(f"Converted PDF to {len(image_paths)} images: {pdf_path}")
        return image_paths, tmp_dir
    except ImportError:
        log.error("pdf2image not installed; cannot convert PDF")
        raise
    except Exception as e:
        log.error(f"PDF conversion failed: {e}")
        raise


def images_to_pdf(image_paths: List[str], output_pdf_path: str) -> None:
    """
    Reconstruct a PDF from a list of image paths.

    Args:
        image_paths: List of image file paths (sorted)
        output_pdf_path: Target PDF output path
    """
    try:
        import img2pdf

        with open(output_pdf_path, "wb") as f:
            f.write(img2pdf.convert(sorted(image_paths)))

        log.info(f"Reconstructed PDF: {output_pdf_path} ({len(image_paths)} pages)")
    except ImportError:
        log.error("img2pdf not installed; cannot reconstruct PDF")
        raise
    except Exception as e:
        log.error(f"PDF reconstruction failed: {e}")
        raise


def validate_file_size(file_path: str, max_size_mb: int = _MAX_FILE_SIZE_MB) -> bool:
    """
    Check if a file is within the size limit.

    Args:
        file_path: Path to the file
        max_size_mb: Maximum size in megabytes

    Returns:
        True if file is within limit, False otherwise
    """
    try:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            log.warning(f"File too large: {file_size_mb:.2f} MB > {max_size_mb} MB")
            return False
        return True
    except Exception as e:
        log.error(f"File size check failed: {e}")
        return False


def get_file_extension(file_path: str) -> str:
    """Get file extension in lowercase, without the leading dot."""
    return Path(file_path).suffix.lower().lstrip(".")


def ensure_output_dir(output_dir: str) -> None:
    """Create output directory if it does not exist."""
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        log.info(f"Output directory ensured: {output_dir}")
    except Exception as e:
        log.error(f"Failed to create output directory: {e}")
        raise


def should_skip_file(file_path: str, skip_keywords: set) -> bool:
    """
    Determine if a file should be skipped based on keywords in its name.

    Args:
        file_path: Path to the file
        skip_keywords: Set of keywords to match (case-insensitive)

    Returns:
        True if file should be skipped, False otherwise
    """
    file_lower = Path(file_path).name.lower()
    for keyword in skip_keywords:
        if keyword.lower() in file_lower:
            log.debug(f"Skipping file (keyword '{keyword}'): {file_path}")
            return True
    return False
