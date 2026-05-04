FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

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

# PaddlePaddle GPU — cu118 index matches working masking-engine; cu121 index unavailable
RUN pip install --no-cache-dir \
    paddlepaddle-gpu==3.2.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cu118/

# PyTorch GPU
RUN pip install --no-cache-dir \
    torch==2.1.2+cu121 \
    torchvision==0.16.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121

COPY services/batch-processor/requirements.txt .
RUN pip install --no-cache-dir \
    -r requirements.txt \
    --extra-index-url https://pypi.org/simple

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
