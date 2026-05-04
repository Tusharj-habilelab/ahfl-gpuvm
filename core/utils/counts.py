# Migrated from: utils/count_pages_in_folder.py + utils/count_processed_files.py (AHFL-Masking 1.0)
# Role: File and page counting utilities used by batch-processor and ops scripts.
"""
utils/counts.py — File and page counting utilities for AHFL-Masking 1.1.
"""

import os


def count_files_in_folder(folder_path: str, extensions=(".pdf", ".jpg", ".jpeg", ".png")) -> dict:
    """
    Recursively count files by type in a folder.

    Returns:
        dict: {"images": int, "pdfs": int, "total": int}
    """
    images, pdfs = 0, 0
    for root, _, files in os.walk(folder_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in (".jpg", ".jpeg", ".png"):
                images += 1
            elif ext == ".pdf":
                pdfs += 1
    return {"images": images, "pdfs": pdfs, "total": images + pdfs}


def count_pdf_pages(pdf_path: str) -> int:
    """Return the number of pages in a PDF file using pdf2image info."""
    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(pdf_path)
        return info.get("Pages", 1)
    except Exception:
        return 1
