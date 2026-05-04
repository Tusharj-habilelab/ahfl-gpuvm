# Migrated from: process_image.py (AHFL-Masking 1.0) — EasyOCR replaced with PaddleOCR
# Role: FastAPI microservice — core masking pipeline. Accepts image/PDF files,
#        runs dual YOLO detection + PaddleOCR, applies masking, returns results.
#        All masking logic imported from core/ — none lives in this file.
#
# GPU Support: Optimized for NVIDIA CUDA inference with torch/PaddlePaddle GPU acceleration
# - Automatic GPU detection and initialization on startup
# - Memory management for long-running inference
# - Fallback to CPU if GPU unavailable
"""
engine.py — Masking Engine FastAPI Service (AHFL-Masking 1.1) with GPU Support

Endpoints:
  POST /mask              — Mask a single file (image or PDF)
  GET  /health            — Health check (includes GPU info)
  GET  /health/detailed   — Detailed GPU metrics

Replaces: process_image.py (1.0) which used EasyOCR and was tightly coupled to main.py.
GPU Optimizations: See GPU_DEPLOYMENT_GUIDE.md for configuration & tuning.
"""

import asyncio
import os
import uuid
import shutil
import tempfile
import gc
import logging
import signal
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from ultralytics import YOLO
import torch

from core import get_yolo_main, get_yolo_best
from core.config import (
    GPU_MEMORY_FRACTION,
    MAX_FILE_SIZE,
    PDF_CHUNK_SIZE,
    validate_required_env_vars,
)

load_dotenv()

# ──────────────────────────────────────────────
# Logging Configuration
# ──────────────────────────────────────────────
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# GPU Configuration & Detection
# ──────────────────────────────────────────────
# Import from core.config — single source of truth; was "false" here vs "true" in
# yolo_runner/paddle, causing YOLO+OCR to run on GPU while engine thought it was CPU.
from core.config import GPU_ENABLED

# Detect available GPUs
CUDA_AVAILABLE = torch.cuda.is_available()
DEVICE_COUNT = torch.cuda.device_count() if CUDA_AVAILABLE else 0
MPS_AVAILABLE = torch.backends.mps.is_available()  # macOS GPU acceleration

# Select device
if CUDA_AVAILABLE and GPU_ENABLED:
    try:
        CUDA_VISIBLE_DEVICES = os.getenv("CUDA_VISIBLE_DEVICES", "0")
        cuda_device = int(CUDA_VISIBLE_DEVICES.split(",")[0])
        DEVICE = f"cuda:{cuda_device}"
        torch.cuda.set_device(cuda_device)
        logger.info(f"✓ Using CUDA device {cuda_device} ({torch.cuda.get_device_name(cuda_device)})")
    except Exception as e:
        logger.warning(f"Could not initialize CUDA device: {e}. Falling back to CPU.")
        DEVICE = "cpu"
elif MPS_AVAILABLE and GPU_ENABLED:
    DEVICE = "mps"
    logger.info("✓ Using macOS Metal Performance Shaders (MPS)")
else:
    DEVICE = "cpu"
    logger.info("ℹ Using CPU inference")

# GPU Memory Settings
if CUDA_AVAILABLE and GPU_ENABLED:
    memory_fraction = GPU_MEMORY_FRACTION
    torch.cuda.set_per_process_memory_fraction(memory_fraction)
    torch.cuda.empty_cache()
    logger.info(f"GPU memory fraction set to {memory_fraction*100:.0f}%")

# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────

app = FastAPI(
    title="AHFL Masking Engine",
    description="PaddleOCR + YOLO masking microservice (GPU-optimized)",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_FOLDER", "./output/masked"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """
    Validate config and initialize GPU, warm up models, and log configuration on startup.
    This ensures GPU kernels are compiled before first inference (avoiding initial latency).
    """
    validate_required_env_vars()

    logger.info("="*60)
    logger.info("🚀 AHFL Masking Engine Starting")
    logger.info("="*60)
    
    # GPU Information
    logger.info("📊 GPU Configuration:")
    logger.info(f"  GPU_ENABLED: {GPU_ENABLED}")
    logger.info(f"  CUDA Available: {CUDA_AVAILABLE}")
    logger.info(f"  Device Count: {DEVICE_COUNT}")
    logger.info(f"  MPS Available: {MPS_AVAILABLE}")
    logger.info(f"  Selected Device: {DEVICE}")
    
    if CUDA_AVAILABLE:
        logger.info(f"  CUDA Version: {torch.version.cuda}")
        logger.info(f"  cuDNN Version: {torch.backends.cudnn.version()}")
        for i in range(DEVICE_COUNT):
            props = torch.cuda.get_device_properties(i)
            logger.info(f"  GPU {i}: {props.name} ({props.total_memory / 1e9:.1f}GB)")
    
    # Model Initialization
    try:
        logger.info("🔧 Pre-loading models...")
        get_yolo_main()
        logger.info("  ✓ YOLO Main model loaded")
        get_yolo_best()
        logger.info("  ✓ YOLO Best model loaded")
    except Exception as e:
        logger.error(f"  ✗ Failed to load models: {e}")
    
    # GPU Warmup (optional but recommended)
    if DEVICE.startswith("cuda") and GPU_ENABLED:
        try:
            logger.info("🔥 Warming up GPU...")
            with torch.no_grad():
                x = torch.randn(1, 3, 640, 640).to(DEVICE)
                del x
                torch.cuda.synchronize()
            torch.cuda.empty_cache()
            logger.info("  ✓ GPU warmup complete")
        except Exception as e:
            logger.warning(f"  ⚠️  GPU warmup skipped: {e}")
    
    logger.info("="*60)
    logger.info("✅ Service Ready")
    logger.info("="*60)


# ──────────────────────────────────────────────
# Internal masking pipeline
# ──────────────────────────────────────────────

def _mask_single_image(image_path: str) -> dict:
    """
    Run the full masking pipeline on a single image file.
    Returns a report dict: {is_number, is_number_masked, is_qr, is_qr_masked, is_xx}

    Delegates all computation to core.pipeline.process_image().
    This wrapper handles file I/O and GPU memory cleanup only.
    """
    import cv2

    try:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")

        from core.pipeline import process_image
        masked_image, report = process_image(image, skip_keywords_enabled=True)

        if not cv2.imwrite(image_path, masked_image):
            raise IOError(f"Failed to write masked image: {image_path}")
        return report

    finally:
        if 'image' in locals():
            del image
        if 'masked_image' in locals():
            del masked_image
        gc.collect()


def _mask_pdf(pdf_path: str) -> dict:
    """Convert PDF to images, mask each in chunks (10 pages at a time), rebuild PDF."""
    from pdf2image import convert_from_path, pdfinfo_from_path
    import img2pdf
    import cv2

    # Check page count first to avoid loading huge PDFs
    try:
        info = pdfinfo_from_path(pdf_path)
        total_pages = info.get("Pages", 0)
    except Exception:
        total_pages = 0

    page_reports = {}
    masked_image_paths = []
    CHUNK_SIZE = PDF_CHUNK_SIZE

    with tempfile.TemporaryDirectory() as tmp_dir:
        page_idx = 0
        start = 1
        end = total_pages if total_pages > 0 else 9999

        # Process in chunks to avoid loading all pages at once
        while start <= end:
            chunk_end = min(start + CHUNK_SIZE - 1, end)
            try:
                pages = convert_from_path(pdf_path, dpi=200, first_page=start, last_page=chunk_end)
            except Exception as e:
                if start == 1:
                    raise  # first chunk failed
                logger.warning(f"PDF chunk {start}-{chunk_end} failed: {e}")
                break

            if not pages:
                break

            for page in pages:
                img_path = os.path.join(tmp_dir, f"p{page_idx:04d}.jpg")
                page.save(img_path, "JPEG")
                del page

                try:
                    report = _mask_single_image(img_path)
                except Exception as e:
                    logger.warning(f"Page {page_idx + 1} error: {e}")
                    report = {"error": str(e)}
                    # Replace with blank image
                    try:
                        import numpy as np
                        blank = np.zeros((2480, 1754, 3), dtype=np.uint8)
                        cv2.imwrite(img_path, blank)
                    except Exception:
                        logger.error(f"Page {page_idx + 1}: masking AND blank replacement failed")

                page_reports[str(page_idx + 1)] = report
                masked_image_paths.append(img_path)
                page_idx += 1

            del pages
            gc.collect()
            start = chunk_end + 1

        # Rebuild PDF from masked images
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(sorted(masked_image_paths)))

    if CUDA_AVAILABLE and GPU_ENABLED:
        torch.cuda.empty_cache()

    return page_reports


# ──────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────

@app.get("/health")
async def health():
    """Basic health check with GPU status."""
    return {
        "status": "ok",
        "service": "masking-engine",
        "version": "1.1.0",
        "gpu_available": CUDA_AVAILABLE or MPS_AVAILABLE,
        "device": DEVICE,
    }


@app.get("/health/detailed")
async def health_detailed() -> Dict[str, Any]:
    """Detailed health metrics including GPU memory and utilization."""
    import psutil
    
    health_info = {
        "status": "healthy",
        "service": "masking-engine",
        "version": "1.1.0",
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
        },
        "gpu": {
            "enabled": GPU_ENABLED,
            "cuda_available": CUDA_AVAILABLE,
            "device_count": DEVICE_COUNT,
            "selected_device": DEVICE,
            "mps_available": MPS_AVAILABLE,
        }
    }
    
    # GPU Memory Metrics (CUDA only)
    if CUDA_AVAILABLE and GPU_ENABLED:
        try:
            device_id = int(DEVICE.split(":")[-1]) if ":" in DEVICE else 0
            allocated = torch.cuda.memory_allocated(device_id)
            reserved = torch.cuda.memory_reserved(device_id)
            total = torch.cuda.get_device_properties(device_id).total_memory
            
            health_info["gpu"].update({
                "memory_allocated_mb": allocated / 1e6,
                "memory_reserved_mb": reserved / 1e6,
                "memory_total_mb": total / 1e6,
                "memory_utilization_percent": (allocated / total) * 100,
            })
        except Exception as e:
            logger.warning(f"Could not retrieve GPU memory metrics: {e}")
            health_info["gpu"]["memory_error"] = str(e)
    
    return health_info


@app.post("/mask")
async def mask_file(file: UploadFile = File(...)):
    """
    Mask Aadhaar numbers and QR codes in an uploaded file.

    Accepts: PDF, JPG, JPEG, PNG (max configured in core.config.MAX_FILE_SIZE)
    Returns: JSON with masking report + output filename
    """
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in ("pdf", "jpg", "jpeg", "png"):
        raise HTTPException(status_code=422, detail=f"Unsupported file type: .{ext}")

    # Check Content-Length before saving (prevents wasting disk I/O)
    content_length = file.file.seek(0, 2)
    file.file.seek(0)
    if content_length > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size {content_length / 1e6:.1f}MB exceeds limit {MAX_FILE_SIZE / 1e6:.1f}MB"
        )

    file_id = str(uuid.uuid4())
    output_filename = f"{file_id}.{ext}"
    output_path = OUTPUT_DIR / output_filename

    # Save file to disk
    with open(output_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    try:
        loop = asyncio.get_event_loop()
        if ext == "pdf":
            page_reports = await loop.run_in_executor(None, _mask_pdf, str(output_path))
        else:
            single_report = await loop.run_in_executor(None, _mask_single_image, str(output_path))
            page_reports = {"1": single_report}

        total_pages = len(page_reports)
        mask_fields = ["is_number_masked", "is_qr_masked"]
        total_masked = sum(
            any(p.get(f, 0) for f in mask_fields)
            for p in page_reports.values()
        )

        return JSONResponse({
            "status": 200,
            "message": "File processed successfully.",
            "fileName": output_filename,
            "total_pages": total_pages,
            "total_pages_masked": total_masked,
            "page_reports": page_reports,
        })

    except Exception as e:
        output_path.unlink(missing_ok=True)
        logger.error("Mask endpoint failed: %s: %s", type(e).__name__, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@app.get("/output/{filename}")
async def get_output_file(filename: str):
    """Return a masked output file by its UUID filename."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(str(file_path))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("engine:app", host="0.0.0.0",
                port=int(os.environ.get("MASKING_ENGINE_PORT", 8001)),
                reload=False)
