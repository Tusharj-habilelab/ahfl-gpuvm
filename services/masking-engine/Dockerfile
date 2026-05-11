# NVIDIA CUDA-based GPU-optimized Dockerfile for Masking Engine
# Supports GPU acceleration for PaddleOCR & YOLO inference
# Base: NVIDIA CUDA 12.2 with cuDNN 8.x
# 
# Usage:
#   docker build -f Dockerfile.gpu -t ahfl-masking-engine:gpu .
#   Requires: docker with --gpus all flag in docker-compose or docker run

FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

LABEL service="masking-engine-gpu" version="1.1.0" description="GPU-accelerated AHFL Masking Engine"

ARG CUDA_HOME=/usr/local/cuda
ENV CUDA_HOME=${CUDA_HOME} \
    PATH=${CUDA_HOME}/bin:${PATH} \
    LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# ──────────────────────────────────────────────
# Layer 1: System dependencies for GPU + ML
# ──────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    wget \
    pkg-config \
    libopenblas-dev \
    liblapack-dev \
    gfortran \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    tesseract-ocr \
    poppler-utils \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python

# ──────────────────────────────────────────────
# Layer 2: Python package manager (pip upgrade)
# ──────────────────────────────────────────────
RUN pip install --upgrade --no-cache-dir pip setuptools wheel

# ──────────────────────────────────────────────
# Layer 3: GPU-optimized PaddlePaddle + dependencies
# ──────────────────────────────────────────────
# PaddlePaddle 3.3.0 GPU — NOT on PyPI, must use official PaddlePaddle index.
# Choose the index matching the host CUDA version:
#   cu118 → CUDA 11.8  |  cu121 → CUDA 12.1/12.2  |  cu126 → CUDA 12.6  |  cu129 → CUDA 12.9
# CUDA 12.2 hosts: use cu121 (correct ABI match; cu118 causes GPU kernel mismatch).
RUN pip install --no-cache-dir \
    paddlepaddle-gpu==3.3.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cu121/

# ──────────────────────────────────────────────
# Layer 4: Deep learning + vision stack (GPU variants)
# ──────────────────────────────────────────────
COPY services/masking-engine/requirements.txt .

# Install Torch from the CUDA-specific PyTorch index here (single source).
RUN pip install --no-cache-dir \
    torch==2.1.2+cu121 \
    torchvision==0.16.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121

# ONNX Runtime / TensorRT intentionally not installed in this image.
RUN pip install --no-cache-dir \
    -r requirements.txt \
    --extra-index-url https://pypi.org/simple

# Build-time validation: ensure core GPU libs import correctly and report CUDA availability.
# These checks validate installs but do not fail on missing CUDA at build time.
RUN python -c "import paddle; print('paddle', getattr(paddle, '__version__', 'unknown'))"
RUN python -c "import torch; print('torch', getattr(torch, '__version__', 'unknown'), 'cuda_available=' + str(torch.cuda.is_available()))"
RUN python -c "from paddleocr import PaddleOCR; print('PaddleOCR OK')"

# ──────────────────────────────────────────────
# Layer 5: Application code + shared core library
# ──────────────────────────────────────────────
COPY services/masking-engine/ .
COPY core/ ./core/

# ──────────────────────────────────────────────
# Layer 6: Health check + optimizations
# ──────────────────────────────────────────────
# Pre-create PaddleOCR model subdirs before VOLUME declaration.
# Dirs created AFTER a VOLUME instruction are not persisted, so this must come first.
RUN mkdir -p /app/models/paddleocr/det \
             /app/models/paddleocr/rec \
             /app/models/paddleocr/cls \
             /app/models/paddleocr/doc_orientation

# Volume mounts for models + outputs
VOLUME ["/app/models", "/app/output"]

# GPU health check: verify CUDA is accessible
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import torch; print(f'GPU Count: {torch.cuda.device_count()}'); assert torch.cuda.is_available(), 'GPU not available'" || exit 1

EXPOSE 8001

# ──────────────────────────────────────────────
# GPU-optimized startup
# ──────────────────────────────────────────────
# Environment: CUDA memory fraction (for inference - can use more)
ENV CUDA_VISIBLE_DEVICES=0 \
    TF_FORCE_GPU_ALLOW_GROWTH=true \
    CUDA_LAUNCH_BLOCKING=0

# Run as root in this closed GPU VM deployment to avoid permission issues with
# mounted /app/models, /root/.paddlex, and output volumes.
# Keep one worker so GPU models are loaded once instead of duplicated per process.
CMD ["uvicorn", "engine:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
