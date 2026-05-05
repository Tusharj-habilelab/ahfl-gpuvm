# Migrated from: bulk.py + bulk-script/bulk1.py + bulk-script/bulk2.py (AHFL-Masking 1.0)
# Role: Canonical batch processing service. Consolidates 3 diverged bulk scripts into one.
#        All masking logic is imported from core/ — zero duplication with the API path.
#        EasyOCR replaced with PaddleOCR via core/ocr_adapter.py + core/masking.py.
"""
batch.py — Batch Processor Service (AHFL-Masking 1.1)

Processes entire folders of documents (PDF / image) for Aadhaar masking,
logs results to DynamoDB, and writes output files.

Usage:
    python batch.py --source <folder> --dest <folder> [--dry-run]

Replaces: bulk.py, bulk-script/bulk1.py, bulk-script/bulk2.py (1.0)
"""

import os
import sys
import uuid
import shutil
import argparse
import tempfile
import logging
import signal
import gc
import math
import time
import threading
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from datetime import datetime, timezone

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
import cv2
import img2pdf
from pdf2image import convert_from_path
from boto3.dynamodb.conditions import Key, Attr
from dotenv import load_dotenv
from ultralytics import YOLO
import torch

# ── Core library imports (single source of truth) ──
from core import (
    get_dynamo_table,
    count_files_in_folder,
    get_yolo_main,
    get_yolo_best,
)
from core.config import (
    BATCH_PATH_SKIP_KEYWORDS,
    GPU_MEMORY_FRACTION,
    GPU_WARMUP_ENABLED,
    MAX_PDF_PAGES,
    MAX_S3_FILE_SIZE,
    PDF_CHUNK_SIZE,
    STALE_PROCESSING_HOURS,
    validate_required_env_vars,
)
from core.pipeline import process_image
from core.db.database import DEFAULT_MASK_COUNTS, build_default_record

load_dotenv()

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("batch-processor")

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

# COMMIT_BATCH_SIZE and GPU_ENABLED imported from core.config — single source of truth.
from core.config import COMMIT_BATCH_SIZE, GPU_ENABLED

TABLE_NAME = os.environ.get("TABLE_NAME", "ahfl_processed_data")  # must match database.py default
MAX_RETRY_ATTEMPTS = 3
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# Bucket names must be set via env vars — no hardcoded defaults to avoid
# leaking AWS account IDs and production resource names into source code.
RAW_BUCKET    = os.environ["RAW_BUCKET"]
MASKED_BUCKET = os.environ["MASKED_BUCKET"]

# ──────────────────────────────────────────────
# GPU Configuration & Graceful Shutdown
# ──────────────────────────────────────────────

# GPU_ENABLED, GPU_MEMORY_FRACTION, GPU_WARMUP_ENABLED imported from core.config above.

CUDA_AVAILABLE = torch.cuda.is_available()
MPS_AVAILABLE = torch.backends.mps.is_available()

if CUDA_AVAILABLE and GPU_ENABLED:
    torch.cuda.set_per_process_memory_fraction(GPU_MEMORY_FRACTION)
    torch.cuda.empty_cache()
    log.info(f"GPU memory fraction: {GPU_MEMORY_FRACTION*100:.0f}%")

# Graceful shutdown flag — allows current file to finish before exit
_shutdown_event = threading.Event()


def _handle_shutdown(signum, frame):
    """Signal handler for graceful shutdown (SIGTERM/SIGINT)."""
    _shutdown_event.set()
    log.info(f"Received signal {signum} — finishing current file then shutting down...")


signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)

# ──────────────────────────────────────────────
# Archive extraction (ZIP/RAR support)
# ──────────────────────────────────────────────

def _unzip(file_path: str, extract_to: str) -> bool:
    """Extract a zip file. Returns True on success."""
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        log.debug(f"Extracted ZIP: {file_path}")
        return True
    except Exception as e:
        log.error(f"Error extracting ZIP {file_path}: {e}")
        shutil.rmtree(extract_to, ignore_errors=True)
        return False


def _extract_path(path_name: str, s3_mode: bool = False) -> None:
    """
    Recursively walk a directory. Extract ZIP files in place.

    Args:
        path_name: Root directory to walk.
        s3_mode: If True, extract-only (don't re-zip). If False, re-zip after processing.
    """
    for root, dirs, files in os.walk(path_name):
        for file in files:
            filepath = os.path.join(root, file)

            if file.endswith(('.zip', '.ZIP')):
                temp_dir = os.path.join(root, f"zip_{os.path.splitext(file)[0]}")
                os.makedirs(temp_dir, exist_ok=True)

                if not _unzip(filepath, temp_dir):
                    continue

                try:
                    _extract_path(temp_dir, s3_mode=s3_mode)

                    if s3_mode:
                        os.remove(filepath)
                        log.debug(f"Removed ZIP {filepath} (S3 mode: extract-only)")
                    else:
                        os.remove(filepath)
                        shutil.make_archive(os.path.splitext(filepath)[0], 'zip', temp_dir)
                        log.debug(f"Re-zipped {filepath} (local mode)")

                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    log.error(f"Error processing ZIP {filepath}: {e}")
                    shutil.rmtree(temp_dir, ignore_errors=True)


# ──────────────────────────────────────────────
# DB helpers — status workflow
# Schema: PK=DOC#{file_path}, SK={createdAt ISO}
# GSI1:   GSI1PK=STATUS#{status}, GSI1SK={createdAt ISO}
# ──────────────────────────────────────────────

def _to_decimal(v):
    """Convert float to Decimal for DynamoDB; guard NaN/Inf."""
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return Decimal(0)
        return Decimal(str(v))
    return v


def _get_skip_paths(table) -> set:
    """Return file paths to skip: COMPLETED or ERROR with retries exhausted.

    Uses GSI1 (GSI1PK = STATUS#{status}) instead of a full table scan —
    O(result set) not O(table size). Requires GSI1 with ProjectionType=ALL.
    """
    skip = set()

    # COMPLETED — skip unconditionally
    kwargs: dict = dict(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq("STATUS#COMPLETED"),
        ProjectionExpression="file_path",
    )
    while True:
        resp = table.query(**kwargs)
        for item in resp.get("Items", []):
            if "file_path" in item:
                skip.add(item["file_path"])
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    # ERROR — skip only if retries exhausted
    kwargs = dict(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq("STATUS#ERROR"),
        ProjectionExpression="file_path, retryAttempts",
    )
    while True:
        resp = table.query(**kwargs)
        for item in resp.get("Items", []):
            if int(item.get("retryAttempts", 0)) >= MAX_RETRY_ATTEMPTS:
                if "file_path" in item:
                    skip.add(item["file_path"])
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    return skip


def _write_pending(table, pk: str, sk: str, file_path: str, s3_key: str = "") -> None:
    """Write initial PENDING record before processing starts."""
    record = build_default_record(pk, sk, file_path, s3_key=s3_key)
    record["id"] = str(uuid.uuid4())
    table.put_item(Item=record)


def _update_to_processing(table, pk: str, sk: str) -> None:
    """Transition PENDING → PROCESSING."""
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET #st = :st, GSI1PK = :gsi1pk, updatedAt = :ts",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":st": "PROCESSING",
            ":gsi1pk": "STATUS#PROCESSING",
            ":ts": now,
        },
    )


def _sanitize_report_for_dynamo(report: dict) -> dict:
    """Convert all floats in a report dict to Decimal for DynamoDB compatibility."""
    sanitized = {}
    for k, v in report.items():
        if isinstance(v, float):
            sanitized[k] = _to_decimal(v)
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_report_for_dynamo(v)
        elif isinstance(v, list):
            sanitized[k] = [
                _sanitize_report_for_dynamo(i) if isinstance(i, dict)
                else _to_decimal(i) if isinstance(i, float)
                else i
                for i in v
            ]
        elif isinstance(v, bool):
            sanitized[k] = v
        else:
            sanitized[k] = v
    return sanitized


def _update_to_completed(
    table, pk: str, sk: str, page_reports: dict, processed_count: list
) -> None:
    """Transition PROCESSING → COMPLETED with nested pageReports and aggregated stats."""
    now = datetime.now(timezone.utc).isoformat()
    total = len(page_reports)
    scanned = sum(1 for p in page_reports.values() if "error" not in p)
    masked = sum(
        1 for p in page_reports.values()
        if p.get("is_number_masked", 0) > 0
        or p.get("is_qr_masked", 0) > 0
        or p.get("ocr_patterns_found", 0) > 0
    )
    is_number = sum(p.get("is_number", 0) for p in page_reports.values())
    is_number_masked = sum(p.get("is_number_masked", 0) for p in page_reports.values())
    is_QR = sum(p.get("is_qr", 0) for p in page_reports.values())
    is_QR_masked = sum(p.get("is_qr_masked", 0) for p in page_reports.values())
    is_XX = sum(p.get("is_xx", 0) for p in page_reports.values())
    ocr_patterns_found = sum(p.get("ocr_patterns_found", 0) for p in page_reports.values())
    is_aadhaar = 1 if any([is_number, is_number_masked, is_QR, is_QR_masked, is_XX, ocr_patterns_found]) else 0

    lane_chosen = "unknown"
    for p in page_reports.values():
        candidate = p.get("lane_chosen")
        if candidate:
            lane_chosen = candidate
            break

    orientation_hint_angle = next(
        (p.get("orientation_hint_angle") for p in page_reports.values() if p.get("orientation_hint_angle") is not None),
        None,
    )
    final_winning_angle = next(
        (p.get("final_winning_angle") for p in page_reports.values() if p.get("final_winning_angle") is not None),
        None,
    )

    skip_reason = next((p.get("skip_reason") for p in page_reports.values() if p.get("skip_reason")), None)
    card_detected = any(bool(p.get("card_detected", False)) for p in page_reports.values())
    aadhaar_verified = any(bool(p.get("aadhaar_verified", False)) for p in page_reports.values())
    pan_found = any(bool(p.get("pan_found", p.get("is_pan", False))) for p in page_reports.values())

    mask_counts = dict(DEFAULT_MASK_COUNTS)
    mask_counts["is_aadhaar"] = int(is_aadhaar)
    mask_counts["is_number"] = int(is_number)
    mask_counts["is_number_masked"] = int(is_number_masked)
    mask_counts["is_qr"] = int(is_QR)
    mask_counts["is_qr_masked"] = int(is_QR_masked)
    mask_counts["is_xx"] = int(is_XX)
    mask_counts["ocr_patterns_found"] = int(ocr_patterns_found)

    # Sanitize nested page reports: strip timing stats (saves space) and convert floats
    sanitized_pages = {
        page_key: _sanitize_report_for_dynamo(
            {k: v for k, v in page_data.items() if k != "stats"}
        )
        for page_key, page_data in page_reports.items()
    }

    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression=(
            "SET #st = :st, GSI1PK = :gsi1pk, updatedAt = :ts, "
            "totalPages = :tp, scannedPages = :sp, maskedPages = :mp, "
            "is_aadhaar = :ia, is_number = :in2, is_number_masked = :inm, "
            "is_QR = :iq, is_QR_masked = :iqm, is_XX = :ix, "
            "ocr_patterns_found = :ocr, pageReports = :pr, mask_counts = :mc, "
            "lane_chosen = :lane, orientation_hint_angle = :oha, final_winning_angle = :fwa, "
            "skip_reason = :sr, card_detected = :cd, aadhaar_verified = :av, pan_found = :pf"
        ),
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":st": "COMPLETED",
            ":gsi1pk": "STATUS#COMPLETED",
            ":ts": now,
            ":tp": total,
            ":sp": scanned,
            ":mp": masked,
            ":ia": is_aadhaar,
            ":in2": is_number,
            ":inm": is_number_masked,
            ":iq": is_QR,
            ":iqm": is_QR_masked,
            ":ix": is_XX,
            ":ocr": ocr_patterns_found,
            ":pr": sanitized_pages,
            ":mc": _sanitize_report_for_dynamo(mask_counts),
            ":lane": lane_chosen,
            ":oha": orientation_hint_angle,
            ":fwa": final_winning_angle,
            ":sr": skip_reason,
            ":cd": card_detected,
            ":av": aadhaar_verified,
            ":pf": pan_found,
        },
    )
    processed_count[0] += 1
    if processed_count[0] % COMMIT_BATCH_SIZE == 0:
        log.info(f"DynamoDB write @ {processed_count[0]} records")


def _update_to_error(table, pk: str, sk: str, error_msg: str) -> None:
    """Transition to ERROR and atomically increment retryAttempts."""
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression=(
            "SET #st = :st, GSI1PK = :gsi1pk, updatedAt = :ts, errorMessage = :em "
            "ADD retryAttempts :one"
        ),
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":st": "ERROR",
            ":gsi1pk": "STATUS#ERROR",
            ":ts": now,
            ":em": error_msg[:1000],
            ":one": 1,
        },
    )


# ──────────────────────────────────────────────
# Model singletons
# ──────────────────────────────────────────────

_models_preloaded = False
_models_preload_lock = threading.Lock()


def preload_models(include_ocr: bool = True, include_yolo: bool = True) -> None:
    """
    Optionally warm model singletons up explicitly.

    This is intentionally NOT called at import time because PaddleOCR startup can
    take a long time and makes `import batch` appear frozen.

    OCR singleton lives in core/pipeline.py — we call its warmup here.
    """
    global _models_preloaded
    if _models_preloaded:
        return

    with _models_preload_lock:
        if _models_preloaded:
            return

        log.info("=" * 80)
        log.info("OPTIONAL MODEL PRELOAD")
        log.info("=" * 80)

        if include_ocr:
            try:
                from core.pipeline import _get_ocr
                log.info("PaddleOCR: Initializing...")
                _get_ocr()
                log.info("PaddleOCR: Ready")
            except Exception as e:
                log.error(f"PaddleOCR initialization failed: {e}")

        if include_yolo:
            log.info("YOLO Main: Initializing...")
            try:
                get_yolo_main()
                log.info("YOLO Main: Ready")
            except Exception as e:
                log.error(f"YOLO Main initialization failed: {e}")

            log.info("YOLO Best: Initializing...")
            try:
                get_yolo_best()
                log.info("YOLO Best: Ready")
            except Exception as e:
                log.error(f"YOLO Best initialization failed: {e}")

            log.info("Front/back classifier: Initializing...")
            try:
                from core.classifiers import _get_classifier
                _get_classifier()
                log.info("✓ Front/back classifier loaded")
            except Exception as e:
                log.error(f"Front/back classifier initialization failed: {e}")

        _models_preloaded = True

        # GPU warmup: run a dummy tensor through CUDA to pre-allocate memory
        if CUDA_AVAILABLE and GPU_ENABLED and GPU_WARMUP_ENABLED:
            try:
                log.info("GPU warmup: pre-allocating CUDA memory...")
                with torch.no_grad():
                    x = torch.randn(1, 3, 640, 640).cuda()
                    del x
                    torch.cuda.synchronize()
                torch.cuda.empty_cache()
                log.info("GPU warmup: complete")
            except Exception as e:
                log.warning(f"GPU warmup skipped: {e}")

        log.info("=" * 80)
        log.info("MODEL PRELOAD COMPLETE")
        log.info("=" * 80)


# ──────────────────────────────────────────────
# Core image masking (single image)
# ──────────────────────────────────────────────

def _process_image(image_path: str) -> dict:
    """
    Run the full masking pipeline on one image via core.pipeline.

    All masking logic lives in core/pipeline.py (single source of truth).
    This wrapper handles only file I/O and GPU memory cleanup.
    """
    try:
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        masked_image, report = process_image(image, skip_keywords_enabled=True)
        if not cv2.imwrite(image_path, masked_image):
            raise IOError(f"cv2.imwrite failed for {image_path}")
        return report

    finally:
        if 'image' in locals():
            del image
        if 'masked_image' in locals():
            del masked_image
        gc.collect()


def _process_pdf(pdf_path: str, dest_path: str) -> dict:
    """Convert PDF → images → mask each → rebuild PDF. Returns per-page report."""
    from pdf2image import pdfinfo_from_path

    # Check page count before loading (fast, no image decode)
    try:
        info = pdfinfo_from_path(pdf_path)
        total_pages = info.get("Pages", 0)
    except Exception:
        total_pages = 0  # proceed and let convert_from_path handle it

    if total_pages > MAX_PDF_PAGES:
        raise ValueError(f"PDF has {total_pages} pages, limit is {MAX_PDF_PAGES}")

    page_reports = {}
    CHUNK_SIZE = PDF_CHUNK_SIZE

    with tempfile.TemporaryDirectory() as tmp:
        image_paths = []
        page_idx = 0

        # Process in chunks to avoid loading all pages into memory at once
        start = 1
        end = total_pages if total_pages > 0 else 9999  # fallback if pdfinfo failed

        while start <= end:
            chunk_end = min(start + CHUNK_SIZE - 1, end)
            try:
                pages = convert_from_path(
                    pdf_path, dpi=200, first_page=start, last_page=chunk_end
                )
            except Exception as e:
                if start == 1 and total_pages == 0:
                    raise  # first chunk failed, re-raise
                log.warning(f"PDF chunk {start}-{chunk_end} failed: {e}")
                break

            if not pages:
                break

            for page in pages:
                img_path = os.path.join(tmp, f"p{page_idx:04d}.jpg")
                page.save(img_path, "JPEG")
                del page

                try:
                    report = _process_image(img_path)
                except Exception as e:
                    log.warning(f"Page {page_idx + 1} error: {e}")
                    report = {"error": str(e)}
                    # Replace with blank image — never include unmasked PII in output PDF
                    try:
                        import numpy as np
                        blank = np.zeros((2480, 1754, 3), dtype=np.uint8)  # A4 at 200dpi
                        cv2.imwrite(img_path, blank)
                    except Exception as blank_err:
                        # Blank write failed (disk full / permissions). Fallback: include
                        # original page so the PDF is complete. Logged clearly for audit.
                        log.error(
                            f"Page {page_idx + 1}: masking failed ({e}) AND blank replacement "
                            f"failed ({blank_err}) — original unmasked page included in output PDF."
                        )
                        page_reports[str(page_idx + 1)] = {
                            **report,
                            "masking_failed": True,
                            "blank_write_failed": True,
                            "original_page_included": True,
                        }
                        image_paths.append(img_path)
                        page_idx += 1
                        continue
                page_reports[str(page_idx + 1)] = report
                image_paths.append(img_path)
                page_idx += 1

            del pages
            gc.collect()
            start = chunk_end + 1

        with open(dest_path, "wb") as f:
            f.write(img2pdf.convert(sorted(image_paths)))

    return page_reports


# ──────────────────────────────────────────────
# PDF helpers
# ──────────────────────────────────────────────


def _is_password_protected_pdf(pdf_path: str) -> bool:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        return reader.is_encrypted
    except Exception:
        return False


# ──────────────────────────────────────────────
# Main batch orchestration
# ──────────────────────────────────────────────


def run_batch(source_dir: str, dest_dir: str, log_to_db: bool = True, dry_run: bool = False):
    """
    Process all documents in source_dir, write masked files to dest_dir.

    Args:
        source_dir: Folder with input files
        dest_dir:   Folder to write masked outputs
        log_to_db:  Whether to write results to DynamoDB
        dry_run:    If True, scan but don't mask
    """
    Path(dest_dir).mkdir(parents=True, exist_ok=True)

    table = None
    skip_paths = set()
    processed_count = [0]

    if log_to_db and not dry_run:
        try:
            table = get_dynamo_table()
            skip_paths = _get_skip_paths(table)
            log.info(f"DynamoDB connected. {len(skip_paths)} files to skip.")
        except Exception as e:
            log.warning(f"DynamoDB unavailable, running without logging: {e}")
            table = None

    stats = count_files_in_folder(source_dir)
    log.info(f"Source: {source_dir} | Files: {stats}")

    for root, _, files in os.walk(source_dir):
        for fname in sorted(files):
            if _shutdown_event.is_set():
                log.info("Graceful shutdown: stopping batch after current file.")
                return

            file_path = os.path.join(root, fname)
            ext = Path(fname).suffix.lower()

            if ext not in SUPPORTED_EXTENSIONS:
                continue
            if file_path in skip_paths:
                log.info(f"[SKIP] Already processed: {fname}")
                continue

            rel = os.path.relpath(file_path, source_dir)
            dest_file = os.path.join(dest_dir, rel)
            Path(dest_file).parent.mkdir(parents=True, exist_ok=True)

            if dry_run:
                log.info(f"[DRY-RUN] Would process: {rel}")
                continue

            # Write PENDING then immediately PROCESSING before work starts
            pk = f"DOC#{file_path}"
            sk = datetime.now(timezone.utc).isoformat()
            if table:
                try:
                    _write_pending(table, pk, sk, file_path)
                    _update_to_processing(table, pk, sk)
                except Exception as db_e:
                    log.warning(f"DynamoDB pre-write failed for {rel}: {db_e}")

            log.info(f"Processing: {rel}")
            try:
                if ext == ".pdf":
                    if _is_password_protected_pdf(file_path):
                        log.warning(f"[SKIP] Password-protected: {rel}")
                        if table:
                            try:
                                _update_to_error(table, pk, sk, "Password-protected PDF")
                            except Exception as db_err:
                                log.error(f"DynamoDB error-write failed for {rel}: {db_err}")
                        continue
                    page_reports = _process_pdf(file_path, dest_file)
                else:
                    # Mask in a temp file first — only move to dest on success
                    tmp_dest = dest_file + ".tmp"
                    shutil.copy2(file_path, tmp_dest)
                    try:
                        report = _process_image(tmp_dest)
                        os.replace(tmp_dest, dest_file)
                    except Exception:
                        if os.path.exists(tmp_dest):
                            os.unlink(tmp_dest)
                        raise
                    page_reports = {"1": report}

                if table:
                    try:
                        _update_to_completed(table, pk, sk, page_reports, processed_count)
                    except Exception as db_e:
                        log.warning(f"DynamoDB update failed for {rel}: {db_e}")
                log.info(f"[OK] {rel}")

            except Exception as e:
                log.error(f"[FAIL] {rel}: {e}")
                if table:
                    try:
                        _update_to_error(table, pk, sk, str(e))
                    except Exception as db_err:
                        log.error(f"DynamoDB error-write failed for {rel}: {db_err}")

            finally:
                # OPTIMIZED: Free memory between file processing
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()

    log.info(f"Batch complete. Records logged: {processed_count[0]}")


# ──────────────────────────────────────────────
# S3 helpers
# ──────────────────────────────────────────────

def _dynamo_retry(fn, *args, attempts: int = 3, **kwargs):
    """
    Call a DynamoDB function with exponential backoff (1s / 2s / 4s).
    Raises the last exception if all attempts fail.
    """
    delay = 1
    last_err = None
    for attempt in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if attempt < attempts - 1:
                log.warning(f"DynamoDB call failed (attempt {attempt+1}/{attempts}): {e} — retrying in {delay}s")
                time.sleep(delay)
                delay *= 2
    raise last_err


def _cleanup_stale_processing_records(table, stale_threshold_hours: int = STALE_PROCESSING_HOURS) -> None:
    """
    Reset PROCESSING records older than stale_threshold_hours back to PENDING.
    Prevents orphaned records from crashes blocking re-processing.
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=stale_threshold_hours)).isoformat()
    scan_kwargs = {
        "FilterExpression": (
            Attr("status").eq("PROCESSING") & Attr("updatedAt").lt(cutoff)
        ),
        "ProjectionExpression": "PK, SK",
    }
    stale_count = 0
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            try:
                now = datetime.now(timezone.utc).isoformat()
                table.update_item(
                    Key={"PK": item["PK"], "SK": item["SK"]},
                    UpdateExpression="SET #st = :st, GSI1PK = :gsi1pk, updatedAt = :ts",
                    ConditionExpression=Attr("status").eq("PROCESSING"),
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={
                        ":st": "PENDING",
                        ":gsi1pk": "STATUS#PENDING",
                        ":ts": now,
                    },
                )
                stale_count += 1
            except ClientError as ce:
                if ce.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    pass  # already transitioned by another instance — safe to ignore
                else:
                    log.error(f"Failed to reset stale record {item.get('PK')}: {ce}")
            except Exception as e:
                log.error(f"Failed to reset stale record {item.get('PK')}: {e}")
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    if stale_count:
        log.warning(f"Reset {stale_count} stale PROCESSING records (older than {stale_threshold_hours}h)")


def _validate_s3_buckets() -> None:
    """
    Pre-flight check: verify both RAW_BUCKET and MASKED_BUCKET are accessible.
    Fails fast before model load or any processing begins.
    Raises RuntimeError if either bucket is unreachable.
    """
    s3 = boto3.client("s3", config=BotoConfig(connect_timeout=10, retries={"max_attempts": 2}))
    for bucket in (RAW_BUCKET, MASKED_BUCKET):
        try:
            s3.head_bucket(Bucket=bucket)
            log.info(f"✓ S3 bucket accessible: {bucket}")
        except ClientError as e:
            code = e.response["Error"]["Code"]
            raise RuntimeError(f"S3 pre-flight failed for bucket '{bucket}' [{code}]: {e}") from e
        except Exception as e:
            raise RuntimeError(f"S3 pre-flight failed for bucket '{bucket}': {e}") from e

def _list_s3_keys(bucket: str, prefix: str = "") -> list:
    """Paginate S3 bucket and return all keys matching SUPPORTED_EXTENSIONS."""
    s3 = boto3.client("s3", config=BotoConfig(read_timeout=120, connect_timeout=10, retries={"max_attempts": 3}))
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if Path(key).suffix.lower() in SUPPORTED_EXTENSIONS:
                keys.append(key)
    return keys


def run_batch_s3(prefix: str = "", log_to_db: bool = True, dry_run: bool = False):
    """
    S3-native batch processing.

    For each file in RAW_BUCKET (filtered by prefix):
      1. Download to a temp file
      2. Run the masking pipeline in-place
      3. Upload the masked result to MASKED_BUCKET under the same key
         (preserves folder structure: 301012320/doc.pdf → 301012320/doc.pdf)

    DynamoDB file_path key = s3://RAW_BUCKET/<key> so dedup works across runs.
    """
    s3 = boto3.client("s3", config=BotoConfig(read_timeout=120, connect_timeout=10, retries={"max_attempts": 3}))
    table = None
    skip_paths = set()
    processed_count = [0]

    if log_to_db and not dry_run:
        try:
            table = get_dynamo_table()
            skip_paths = _get_skip_paths(table)
            log.info(f"DynamoDB connected. {len(skip_paths)} files to skip.")
            _cleanup_stale_processing_records(table)
        except Exception as e:
            log.warning(f"DynamoDB unavailable, running without logging: {e}")
            table = None

    log.info(f"Listing s3://{RAW_BUCKET}/{prefix}")
    keys = _list_s3_keys(RAW_BUCKET, prefix)
    log.info(f"Found {len(keys)} files to process")

    for s3_key in sorted(keys):
        if _shutdown_event.is_set():
            log.info("Graceful shutdown: stopping S3 batch after current file.")
            return

        s3_file_path = f"s3://{RAW_BUCKET}/{s3_key}"

        if s3_file_path in skip_paths:
            log.info(f"[SKIP] Already processed: {s3_key}")
            continue

        if dry_run:
            log.info(f"[DRY-RUN] Would process: {s3_key}")
            continue

        # Path-based skip filter (mirrors bulk.py to_skip_file): skip files whose
        # S3 key contains any of these keywords in folder names or filename.
        # This runs before download — no head_object call wasted on excluded files.
        _key_lower = s3_key.lower()
        _matched_keyword = next((kw for kw in BATCH_PATH_SKIP_KEYWORDS if kw in _key_lower), None)
        if _matched_keyword:
            log.info(f"[SKIP] Path keyword '{_matched_keyword}': {s3_key}")
            if table:
                _sk_skip = datetime.now(timezone.utc).isoformat()
                try:
                    _dynamo_retry(_write_pending, table, f"DOC#{s3_file_path}", _sk_skip, s3_file_path, s3_key=s3_key)
                    _dynamo_retry(_update_to_error, table, f"DOC#{s3_file_path}", _sk_skip, f"Skipped: path keyword '{_matched_keyword}'")
                except Exception as db_e:
                    log.warning(f"DynamoDB skip-write failed for {s3_key}: {db_e}")
            continue

        ext = Path(s3_key).suffix.lower()
        pk = f"DOC#{s3_file_path}"
        sk = datetime.now(timezone.utc).isoformat()

        if table:
            try:
                _dynamo_retry(_write_pending, table, pk, sk, s3_file_path, s3_key=s3_key)
                _dynamo_retry(_update_to_processing, table, pk, sk)
            except Exception as db_e:
                log.warning(f"DynamoDB pre-write failed for {s3_key}: {db_e}")

        log.info(f"Processing: {s3_key}")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                local_input = os.path.join(tmp, Path(s3_key).name)

                # Size guard: reject files > MAX_S3_FILE_SIZE
                head = s3.head_object(Bucket=RAW_BUCKET, Key=s3_key)
                file_size = head["ContentLength"]
                if file_size > MAX_S3_FILE_SIZE:
                    raise ValueError(f"File too large: {file_size} bytes exceeds {MAX_S3_FILE_SIZE}")

                # Download
                s3.download_file(RAW_BUCKET, s3_key, local_input)
                log.debug(f"Downloaded: {s3_key}")

                # Process
                if ext == ".pdf":
                    if _is_password_protected_pdf(local_input):
                        log.warning(f"[SKIP] Password-protected: {s3_key}")
                        if table:
                            try:
                                _update_to_error(table, pk, sk, "Password-protected PDF")
                            except Exception as db_err:
                                log.error(f"DynamoDB error-write failed for {s3_key}: {db_err}")
                        continue
                    local_output = os.path.join(tmp, "masked_" + Path(s3_key).name)
                    page_reports = _process_pdf(local_input, local_output)
                    upload_path = local_output
                else:
                    # _process_image() masks in-place
                    page_reports = {"1": _process_image(local_input)}
                    upload_path = local_input

                # Upload directly to final key in MASKED_BUCKET.
                # No S3 staging object is created, copied, or deleted.
                try:
                    s3.upload_file(upload_path, MASKED_BUCKET, s3_key)
                    log.debug(f"Uploaded → s3://{MASKED_BUCKET}/{s3_key}")
                except ClientError as s3_err:
                    code = s3_err.response["Error"]["Code"]
                    log.error(f"S3 upload failed for {s3_key} [{code}]: {s3_err}")
                    raise

                if table:
                    try:
                        _dynamo_retry(_update_to_completed, table, pk, sk, page_reports, processed_count)
                    except Exception as db_e:
                        log.error(f"DynamoDB completed-write failed for {s3_key}: {db_e}")
                log.info(f"[OK] {s3_key}")

        except Exception as e:
            log.error(f"[FAIL] {s3_key}: {e}")
            if table:
                try:
                    _update_to_error(table, pk, sk, str(e))
                except Exception as db_err:
                    log.error(f"DynamoDB error-write failed for {s3_key}: {db_err}")

        finally:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()

    log.info(f"S3 batch complete. Records logged: {processed_count[0]}")


# ──────────────────────────────────────────────
# CLI entrypoint
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # Validate required env vars at startup (fail fast)
    validate_required_env_vars()

    parser = argparse.ArgumentParser(description="AHFL-Masking 1.1 Batch Processor")
    parser.add_argument("--s3",    action="store_true", help="S3 mode: read from RAW_BUCKET, write to MASKED_BUCKET")
    parser.add_argument("--prefix", default="", help="S3 key prefix to filter (e.g. '301012320/'). Only used with --s3")
    parser.add_argument("--source", default="", help="Source folder (local mode only)")
    parser.add_argument("--dest",   default="", help="Destination folder (local mode only)")
    parser.add_argument("--no-db",  action="store_true", help="Disable DB logging")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, do not mask")
    parser.add_argument(
        "--no-preload-models",
        action="store_true",
        help="Skip explicit model warm-up before batch processing starts",
    )
    parser.add_argument(
        "--gpu-memory-fraction",
        type=float,
        default=None,
        help="GPU memory fraction (0.0-1.0). Overrides TORCH_CUDA_MAX_MEMORY_FRAC env var.",
    )
    args = parser.parse_args()

    # Apply CLI GPU memory fraction override
    if args.gpu_memory_fraction is not None and CUDA_AVAILABLE:
        torch.cuda.set_per_process_memory_fraction(args.gpu_memory_fraction)
        log.info(f"GPU memory fraction overridden via CLI: {args.gpu_memory_fraction*100:.0f}%")

    if not args.s3 and (not args.source or not args.dest):
        parser.error("--source and --dest are required in local mode (or use --s3)")

    if not args.no_preload_models and not args.dry_run:
        if args.s3:
            _validate_s3_buckets()
        preload_models()

    if args.s3:
        run_batch_s3(
            prefix=args.prefix,
            log_to_db=not args.no_db,
            dry_run=args.dry_run,
        )
    else:
        run_batch(
            source_dir=args.source,
            dest_dir=args.dest,
            log_to_db=not args.no_db,
            dry_run=args.dry_run,
        )
