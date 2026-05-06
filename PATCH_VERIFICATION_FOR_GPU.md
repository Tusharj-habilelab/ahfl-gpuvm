# Patch Verification & Deployment for GPU Server

**Date:** 2026-05-05  
**Status:** All local patches verified and fixed. Ready for GPU deployment.

---

## LOCAL CODE AUDIT — COMPLETED ✓

All critical patches are now in place locally:

### 1. PaddleOCR GPU Device Hardcoding ✓
**File:** `core/ocr/paddle.py` (lines 27-39 & 55-57)

```python
# create_paddle_ocr() — device hardcoded to gpu:0
device="gpu:0",
det_model_dir=os.path.join(_model_dir, "det"),
rec_model_dir=os.path.join(_model_dir, "rec"),
cls_model_dir=os.path.join(_model_dir, "cls"),

# get_doc_orientation_model() — device hardcoded to gpu:0
device="gpu:0",
```

**Action on GPU:** Copy this file to `/data-disk/ahfl_deploy_gpu/core/ocr/paddle.py`

---

### 2. RGB Conversion for Grayscale PDFs ✓
**File:** `core/utils/file_utils.py` (line 49)

```python
page.convert('RGB').save(img_path, "JPEG")  # Force RGB (3 channels for YOLO)
```

**Why:** PDF pages convert to grayscale (1 channel) by default. YOLO requires 3 channels (RGB). Without this, YOLO fails with "expected 3 channels, got 1 channels".

**Action on GPU:** Copy this file to `/data-disk/ahfl_deploy_gpu/core/utils/file_utils.py`

---

### 3. Batch Processor Validation & Archive Support ✓
**File:** `services/batch-processor/batch.py`

**Line 29:** `import zipfile` — enables ZIP archive extraction  
**Line 60:** `validate_required_env_vars` import  
**Line 125-135:** `_unzip()` function for ZIP extraction  
**Line 960:** `validate_required_env_vars()` called at startup (fail-fast on missing env vars)

**Action on GPU:** Copy this file to `/data-disk/ahfl_deploy_gpu/services/batch-processor/batch.py`

---

### 4. Masking Engine GPU Configuration ✓
**File:** `services/masking-engine/engine.py` (line 61)

```python
from core.config import GPU_ENABLED
```

**Why:** Single source of truth. Previously had split-brain bug (engine.py "false", core modules "true").

**Action on GPU:** Copy this file to `/data-disk/ahfl_deploy_gpu/services/masking-engine/engine.py`

---

### 5. S3 Upload — Direct (No Staging) ✓
**File:** `services/batch-processor/batch.py` (line 929)

```python
# No S3 staging object is created, copied, or deleted.
```

**Verified:** No staging copy/delete pattern. Upload goes directly to masked bucket.

---

## GPU SERVER DEPLOYMENT — NEXT STEPS

### Phase 1: Copy Patched Files (5 minutes)

```bash
cd /data-disk/ahfl_deploy_gpu/

# Copy all patched files from local repo
# Option A: Manual copy (if SSH available)
scp core/ocr/paddle.py user@gpu:/data-disk/ahfl_deploy_gpu/core/ocr/
scp core/utils/file_utils.py user@gpu:/data-disk/ahfl_deploy_gpu/core/utils/
scp services/batch-processor/batch.py user@gpu:/data-disk/ahfl_deploy_gpu/services/batch-processor/
scp services/masking-engine/engine.py user@gpu:/data-disk/ahfl_deploy_gpu/services/masking-engine/

# Option B: Manual file edits on GPU server
# SSH into GPU, open each file in nano/vi, copy-paste changes
```

---

### Phase 2: Verify File Changes (2 minutes)

**On GPU server:**

```bash
# Verify paddle.py has model_dir params
grep -A 3 "det_model_dir" /data-disk/ahfl_deploy_gpu/core/ocr/paddle.py
# Expected: det_model_dir, rec_model_dir, cls_model_dir all present

# Verify RGB conversion in file_utils.py
grep "page.convert.*RGB" /data-disk/ahfl_deploy_gpu/core/utils/file_utils.py
# Expected: page.convert('RGB').save(...)

# Verify batch.py has validation
grep "validate_required_env_vars()" /data-disk/ahfl_deploy_gpu/services/batch-processor/batch.py
# Expected: found on line ~960

# Verify engine.py GPU_ENABLED
grep "from core.config import GPU_ENABLED" /data-disk/ahfl_deploy_gpu/services/masking-engine/engine.py
# Expected: found on line 61
```

---

### Phase 3: Rebuild Docker Images (15 minutes)

**On GPU server:**

```bash
cd /data-disk/ahfl_deploy_gpu/

# Build batch-processor with all patches
docker build -t ahfl-batch-processor:d4-patched services/batch-processor/
# Expected build log should show no errors

# Build masking-engine with all patches
docker build -t ahfl-masking-engine:d4-patched services/masking-engine/
# Expected build log should show no errors

# Verify images created
docker images | grep d4-patched
# Expected: both ahfl-batch-processor and ahfl-masking-engine with d4-patched tag
```

---

### Phase 4: Dry Run Test (5 minutes)

```bash
# Stop old containers
docker stop ahfl-batch-processor ahfl-masking-engine 2>/dev/null || true

# Start masking-engine (dependency)
docker run -d \
  --name ahfl-masking-engine-d4-patched \
  --gpus all \
  -e GPU_ENABLED=true \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e LOG_LEVEL=DEBUG \
  -v /app/models:/app/models \
  -p 8001:8001 \
  ahfl-masking-engine:d4-patched

sleep 3

# Check GPU allocation
docker logs ahfl-masking-engine-d4-patched | grep -i "cuda\|gpu:0\|device"
# Expected: "Using CUDA device 0", "gpu:0" mentions

# Dry run (no uploads, no DB writes)
docker run --rm \
  --gpus all \
  --name ahfl-batch-processor-dryrun-d4 \
  -e AWS_REGION=us-east-1 \
  -e RAW_BUCKET=uat_raw \
  -e MASKED_BUCKET=uat_masked \
  -e TABLE_NAME=ahfl_processed_data \
  -e GPU_ENABLED=true \
  -e LOG_LEVEL=DEBUG \
  -v /app/models:/app/models \
  -v $(pwd)/logs:/logs \
  ahfl-batch-processor:d4-patched \
  python services/batch-processor/batch.py \
    --source s3://uat_raw/test_sample/ \
    --dry-run

# Check logs
tail -50 /data-disk/ahfl_deploy_gpu/logs/batch.log | grep -E "DRY RUN|validate_required|RGB|device"
# Expected: No S3 uploads, no DynamoDB writes, GPU device mentions
```

---

### Phase 5: Single Image Test (15 minutes)

```bash
# Upload test image if not present
aws s3 ls s3://uat_raw/test_sample/test_aadhaar.jpg --region us-east-1 || \
  aws s3 cp ~/test_aadhaar.jpg s3://uat_raw/test_sample/test_aadhaar.jpg --region us-east-1

# Process single image
docker run --rm \
  --gpus all \
  --name ahfl-batch-processor-test-d4 \
  -e AWS_REGION=us-east-1 \
  -e RAW_BUCKET=uat_raw \
  -e MASKED_BUCKET=uat_masked \
  -e TABLE_NAME=ahfl_processed_data \
  -e GPU_ENABLED=true \
  -e LOG_LEVEL=DEBUG \
  -v /app/models:/app/models \
  -v $(pwd)/logs:/logs \
  ahfl-batch-processor:d4-patched \
  python services/batch-processor/batch.py \
    --source s3://uat_raw/test_sample/test_aadhaar.jpg

# Monitor GPU
watch -n 1 nvidia-smi

# Expected in logs:
# ✓ PaddleOCR loaded on gpu:0 (from paddle.py device="gpu:0")
# ✓ DocImgOrientationClassification loaded on gpu:0
# ✓ OCR inference: < 2s (GPU speed)
# ✓ YOLO detection: < 1s (GPU speed)
# ✓ RGB conversion applied (from file_utils.py patch)
# ✓ Uploaded → s3://uat_masked/test_sample/test_aadhaar.jpg (DIRECT, no staging)
```

---

## VERIFICATION CHECKLIST

✓ All 5 patches present in local repo  
✓ paddle.py has model_dir parameters (det/rec/cls paths set)  
✓ RGB conversion in file_utils.py  
✓ Batch validation + zipfile support  
✓ Engine GPU_ENABLED from core.config  
✓ Docker volume mounts configured correctly  

**Ready for GPU deployment:** YES

---

## ROLLBACK (if issues)

```bash
cd /data-disk/ahfl_deploy_gpu/
git checkout main -- core/ocr/paddle.py core/utils/file_utils.py services/batch-processor/batch.py services/masking-engine/engine.py
docker build -t ahfl-batch-processor:main services/batch-processor/
docker build -t ahfl-masking-engine:main services/masking-engine/
```
