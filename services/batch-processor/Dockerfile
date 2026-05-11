#FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04
FROM nvidia/cuda:12.2.2-cudnn8-devel-ubuntu22.04

LABEL service="batch-processor" version="1.1.0"

ARG CUDA_HOME=/usr/local/cuda
ENV CUDA_HOME=${CUDA_HOME} \
    PATH=${CUDA_HOME}/bin:${PATH} \
    LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

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

RUN pip install --upgrade --no-cache-dir pip setuptools wheel

# PaddlePaddle GPU — cu121 channel does not publish paddlepaddle-gpu 3.3.0.
# Use cu126 channel (validated package exists for cp310 linux_x86_64).
# Single source install in Dockerfile; keep commented in requirements.txt.
RUN pip install --no-cache-dir \
    paddlepaddle-gpu==3.3.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cu126/

# PyTorch GPU
# Single source install in Dockerfile; keep commented in requirements.txt.
RUN pip install --no-cache-dir \
    torch==2.1.2+cu121 \
    torchvision==0.16.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121

COPY services/batch-processor/requirements.txt .
# ONNX Runtime / TensorRT intentionally not installed in this image.
RUN pip install --no-cache-dir \
    -r requirements.txt \
    --extra-index-url https://pypi.org/simple

# Build-time validation: ensure core GPU libs import correctly and report CUDA availability.
# These checks validate installs but do not fail on missing CUDA at build time.
#RUN python -c "import paddle; print('paddle', getattr(paddle, '__version__', 'unknown'))"
#RUN python -c "import torch; print('torch', getattr(torch, '__version__', 'unknown'), 'cuda_available=' + str(torch.cuda.is_available()))"
#RUN python -c "from paddleocr import PaddleOCR; print('PaddleOCR OK')"

COPY services/batch-processor/ .
COPY core/ ./core/

ENV CUDA_VISIBLE_DEVICES=0 \
    TF_FORCE_GPU_ALLOW_GROWTH=true \
    CUDA_LAUNCH_BLOCKING=0

VOLUME ["/app/models"]

# Run as root in this closed GPU VM deployment to avoid permission issues with
# mounted model and PaddleOCR cache volumes.
ENTRYPOINT ["python", "batch.py"]
CMD ["--s3"]