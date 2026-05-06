# GPU Deployment Changes — D4 Branch
**Date:** 2026-05-04  
**Branch:** D4-testing-with-d1-params-and-paddle-version  
**Commit:** 0368dd2 (04052026-D4 gpu)

---

## Summary
Three critical fixes for GPU consistency and S3 upload reliability:
1. **PaddleOCR GPU device handling** — hardcode gpu:0, remove CPU fallback
2. **PaddlePaddle CUDA ABI** — upgrade to 3.3.0 cu121 (CUDA 12.2 host match)
3. **S3 upload simplification** — remove staging copy/delete, upload directly

---

## Changes Made

### 1. core/ocr/paddle.py — GPU Device Hardcoding

**Reason:** PaddleOCR was conditionally choosing CPU/GPU based on config. This caused split-brain:
- Engine sees GPU_ENABLED=true, runs on GPU
- Some code paths fell back to CPU
- Model loading inconsistency across services

**Changes:**
- `create_paddle_ocr()`: Changed from `device="gpu:0" if _use_gpu else "cpu"` → always `device="gpu:0"`
- `get_doc_orientation_model()`: Now explicitly sets `device="gpu:0"` and loads from PADDLE_MODEL_DIR/doc_orientation (volume-mounted, no auto-download)
- Removed conditional GPU_ENABLED import for PaddleOCR — always GPU

**Files affected:**
```
core/ocr/paddle.py:30–40 (create_paddle_ocr)
core/ocr/paddle.py:48–62 (get_doc_orientation_model)
```

**Impact:** All PaddleOCR calls now deterministically run on GPU. No more CPU fallback surprises.

---

### 2. services/batch-processor/Dockerfile — PaddlePaddle CUDA ABI Fix

**Reason:** Batch processor had cu118 (CUDA 11.8) while host runs CUDA 12.2. Caused ABI mismatch, leading to silent GPU fallback.

**Changes:**
```dockerfile
# OLD:
paddlepaddle-gpu==3.2.0 \
-i https://www.paddlepaddle.org.cn/packages/stable/cu118/

# NEW:
paddlepaddle-gpu==3.3.0 \
-i https://www.paddlepaddle.org.cn/packages/stable/cu121/
```

**Why cu121:** cu121 = CUDA 12.1, closest match to host CUDA 12.2 available in PaddlePaddle index.

**Files affected:**
```
services/batch-processor/Dockerfile:40–42
```

**Impact:** Batch processor now loads PaddlePaddle GPU ops directly; no CPU fallback. Version bump (3.2.0 → 3.3.0) includes bug fixes.

---

### 3. services/batch-processor/batch.py — S3 Upload Simplification

**Reason:** Staging key (copy → delete) pattern was:
- Extra S3 API calls (upload, copy, delete = 3 ops instead of 1)
- Adds latency and failure points
- Not needed — upload directly to final location

**Changes:**
```python
# OLD:
staging_key = f"_staging/{uuid.uuid4()}/{s3_key}"
s3.upload_file(upload_path, MASKED_BUCKET, staging_key)
s3.copy_object(Bucket=MASKED_BUCKET, CopySource=..., Key=s3_key)
s3.delete_object(Bucket=MASKED_BUCKET, Key=staging_key)

# NEW:
s3.upload_file(upload_path, MASKED_BUCKET, s3_key)
```

**Files affected:**
```
services/batch-processor/batch.py:926–933
```

**Impact:** 33% fewer S3 API calls, lower latency, simpler error handling.

---

## Deployment Steps

### Step 1: Pull Latest Code
```bash
cd /path/to/gpu-server
git fetch origin
git checkout D4-testing-with-d1-params-and-paddle-version
git reset --hard origin/D4-testing-with-d1-params-and-paddle-version
```

### Step 2: Rebuild Docker Images
```bash
# Batch processor (includes PaddlePaddle cu121 fix)
docker build -t ahfl-batch-processor:d4 services/batch-processor/

# Masking engine (no Dockerfile changes, but pull latest code)
docker build -t ahfl-masking-engine:d4 services/masking-engine/
```

### Step 3: Run Containers
```bash
# Stop old containers
docker stop ahfl-batch-processor ahfl-masking-engine

# Start new containers with rebuilt images
docker run -d \
  --name ahfl-batch-processor \
  --gpus all \
  -e GPU_ENABLED=true \
  -e CUDA_VISIBLE_DEVICES=0 \
  -v /app/models:/app/models \
  ahfl-batch-processor:d4

docker run -d \
  --name ahfl-masking-engine \
  --gpus all \
  -e GPU_ENABLED=true \
  -e CUDA_VISIBLE_DEVICES=0 \
  -v /app/models:/app/models \
  -p 8001:8001 \
  ahfl-masking-engine:d4
```

### Step 4: Verify GPU Usage
```bash
# Check GPU memory allocation (should show both containers using GPU)
nvidia-smi

# Check logs for GPU device confirmation
docker logs ahfl-masking-engine | grep "CUDA\|GPU\|device"
docker logs ahfl-batch-processor | grep "CUDA\|GPU\|device"

# Expected:
# ✓ Using CUDA device 0 (Tesla T4 / A100 / etc)
# ✓ GPU memory allocated: XXX MB
```

### Step 5: Test End-to-End
```bash
# Masking engine health check
curl http://localhost:8001/health/detailed

# Expected response: "device": "cuda:0", "memory_allocated_mb": XXX

# Batch processor dry run
python services/batch-processor/batch.py \
  --source s3://raw-bucket/test/ \
  --dry-run
```

---

## Rollback (if needed)
```bash
git checkout main
git reset --hard origin/main
docker build -t ahfl-batch-processor:main services/batch-processor/
docker build -t ahfl-masking-engine:main services/masking-engine/
# Restart containers with :main tag
```

---

## Testing Checklist
- [ ] GPU memory allocation confirmed (nvidia-smi)
- [ ] PaddleOCR running on GPU (check logs for model load)
- [ ] Batch processor S3 uploads complete without staging copies
- [ ] No CPU fallback warnings in logs
- [ ] OCR inference latency < 2s per page (GPU) vs > 10s (CPU)
- [ ] End-to-end masking on 5 test PDFs succeeds

---

## Files to Deploy
```
✓ core/ocr/paddle.py
✓ services/batch-processor/Dockerfile
✓ services/batch-processor/batch.py
✓ All core/ modules (no changes, but redeploy for consistency)
✓ All services/ modules (no changes except batch-processor, but redeploy)
```

## Do NOT Deploy
```
✗ graphify-out/* (internal documentation, not part of app)
✗ test_current_version.ipynb (test artifact only)
```
