# D4 GPU DEPLOYMENT & TESTING WORKFLOW
**Date:** 2026-05-04  
**Changes:** PaddleOCR GPU hardcoding + CUDA ABI fix + S3 upload simplification

---

## 1. APPLY PATCHES ON GPU SERVER

### Step 1.1: Copy Patches to GPU
On GPU server `/data-disk/ahfl_deploy_gpu/`:
```bash
# Option A: Copy patch code directly into GPU_MASTER_SYNC.py
# Open D4_PATCHES_FOR_GPU.py, copy the 3 patch() blocks
# Insert into GPU_MASTER_SYNC.py at line 651 (before REPORT section)

# Option B: Automated append
cat D4_PATCHES_FOR_GPU.py | grep -A 100 "# PATCH D4" >> GPU_MASTER_SYNC.py
# Then manually remove the header comment block
```

### Step 1.2: Run Master Sync
```bash
cd /data-disk/ahfl_deploy_gpu/
python3 GPU_MASTER_SYNC.py
```

**Expected output:**
```
============================================================
GPU MASTER SYNC PATCH REPORT
============================================================
✓ D4.1 — paddle.py: GPU device hardcoded (remove CPU fallback)
✓ D4.2 — paddle.py: DocImgOrientationClassification GPU device + model path
✓ D4.3 — batch.py: S3 upload direct (no staging copy/delete)

Applied: 3 | Failed: 0
============================================================
ALL PATCHES APPLIED. Rebuild Docker and re-run test.
============================================================
```

---

## 2. REBUILD DOCKER IMAGES

```bash
cd /data-disk/ahfl_deploy_gpu/

# Batch processor (CRITICAL: Dockerfile has PaddlePaddle cu121 upgrade)
docker build -t ahfl-batch-processor:d4 services/batch-processor/

# Masking engine (code changes applied, rebuild for consistency)
docker build -t ahfl-masking-engine:d4 services/masking-engine/

# Verify images
docker images | grep d4
```

---

## 3. VERIFY WITH DRY RUN

```bash
# Stop running containers
docker stop ahfl-batch-processor ahfl-masking-engine

# Run masking-engine first (dependency)
docker run -d \
  --name ahfl-masking-engine-d4 \
  --gpus all \
  -e GPU_ENABLED=true \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e LOG_LEVEL=DEBUG \
  -v /app/models:/app/models \
  -p 8001:8001 \
  ahfl-masking-engine:d4

# Wait for startup
sleep 5

# Check GPU allocation
docker logs ahfl-masking-engine-d4 | grep -i "cuda\|gpu\|device"
```

**Expected logs:**
```
✓ Using CUDA device 0 (Tesla T4)
✓ GPU memory fraction set to 70%
✓ YOLO Main model loaded
✓ YOLO Best model loaded
```

### 3.1: Dry Run (no actual processing, S3 upload skipped)
```bash
docker run --rm \
  --gpus all \
  --name ahfl-batch-processor-dryrun \
  -e AWS_REGION=us-east-1 \
  -e RAW_BUCKET=uat_raw \
  -e MASKED_BUCKET=uat_masked \
  -e TABLE_NAME=ahfl_processed_data \
  -e GPU_ENABLED=true \
  -e LOG_LEVEL=DEBUG \
  -v /app/models:/app/models \
  -v $(pwd)/logs:/logs \
  ahfl-batch-processor:d4 \
  python services/batch-processor/batch.py \
    --source s3://uat_raw/test_sample/ \
    --dry-run

# Check logs
tail -100 /data-disk/ahfl_deploy_gpu/logs/batch.log
```

**Expected behavior:**
- List files from S3 uat_raw/test_sample/
- Print "DRY RUN — no files will be processed"
- No S3 uploads
- No DynamoDB writes

---

## 4. TEST WITH ONE IMAGE FROM S3

### Step 4.1: Upload Test Image to S3
```bash
# Check what's in uat_raw
aws s3 ls s3://uat_raw/test_sample/ --region us-east-1

# If empty, upload test image
aws s3 cp ~/test_aadhaar.jpg s3://uat_raw/test_sample/test_aadhaar.jpg --region us-east-1
```

### Step 4.2: Run Real Processing (single image)
```bash
docker run --rm \
  --gpus all \
  --name ahfl-batch-processor-test \
  -e AWS_REGION=us-east-1 \
  -e RAW_BUCKET=uat_raw \
  -e MASKED_BUCKET=uat_masked \
  -e TABLE_NAME=ahfl_processed_data \
  -e GPU_ENABLED=true \
  -e LOG_LEVEL=DEBUG \
  -v /app/models:/app/models \
  -v $(pwd)/logs:/logs \
  ahfl-batch-processor:d4 \
  python services/batch-processor/batch.py \
    --source s3://uat_raw/test_sample/test_aadhaar.jpg

# Monitor GPU
watch -n 1 nvidia-smi
```

---

## 5. VERIFICATION CHECKLIST

### 5.1: GPU Metrics
- [ ] `nvidia-smi` shows both batch-processor and masking-engine using GPU memory
- [ ] GPU memory allocated < 4000MB (not hitting OOM)
- [ ] GPU utilization > 0% during inference

```bash
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu,utilization.memory \
  --format=csv,noheader,nounits
```

### 5.2: Logging Output

**Expected in docker logs:**
```
✓ PaddleOCR loaded on gpu:0
✓ DocImgOrientationClassification loaded on gpu:0
✓ Processing: s3://uat_raw/test_sample/test_aadhaar.jpg
✓ OCR inference: 1.2s (GPU, fast)
✓ YOLO detection: 0.8s (GPU)
✓ Masking complete
✓ Uploaded → s3://uat_masked/test_sample/test_aadhaar.jpg (DIRECT, no staging)
```

**Check logs:**
```bash
docker logs ahfl-batch-processor-test | grep -E "CUDA|gpu|device|inference|Uploaded"
tail -50 /data-disk/ahfl_deploy_gpu/logs/batch.log
```

### 5.3: Database Entry (DynamoDB)

Check if record was written:
```bash
aws dynamodb get-item \
  --table-name ahfl_processed_data \
  --key '{
    "s3_key": {"S": "s3://uat_raw/test_sample/test_aadhaar.jpg"}
  }' \
  --region us-east-1
```

**Expected fields:**
```json
{
  "s3_key": "s3://uat_raw/test_sample/test_aadhaar.jpg",
  "masked_s3_key": "s3://uat_masked/test_sample/test_aadhaar.jpg",
  "status": "COMPLETED",
  "timestamp": "2026-05-04T15:30:00Z",
  "is_number_masked": 1,
  "is_qr_masked": 0,
  "lane_chosen": "form",
  "router_confidence": 0.95,
  "mask_counts": { "is_aadhaar": 1, "is_number_masked": 1, "is_qr_masked": 0 }
}
```

### 5.4: Logging Records

Check what was logged:
```bash
# Batch processor stdout
docker exec ahfl-batch-processor-test tail -50 /var/log/batch.log 2>/dev/null

# Expected entries:
# [INFO] s3://uat_raw/test_sample/test_aadhaar.jpg — PROCESSING
# [DEBUG] OCR inference: 1.234s (GPU)
# [DEBUG] YOLO gate: 0.891s (GPU)
# [INFO] s3://uat_raw/test_sample/test_aadhaar.jpg — COMPLETED (uploaded to uat_masked)
# [INFO] DynamoDB write: 1 row
```

### 5.5: Masked Output File

Download from S3 and verify:
```bash
aws s3 cp s3://uat_masked/test_sample/test_aadhaar.jpg ~/masked_aadhaar.jpg --region us-east-1

# Verify file exists and has black boxes (visual inspection)
file ~/masked_aadhaar.jpg
ls -lh ~/masked_aadhaar.jpg
```

---

## 6. FULL BATCH RUN (after single image test passes)

```bash
docker run -d \
  --name ahfl-batch-processor-prod \
  --gpus all \
  -e AWS_REGION=us-east-1 \
  -e RAW_BUCKET=uat_raw \
  -e MASKED_BUCKET=uat_masked \
  -e TABLE_NAME=ahfl_processed_data \
  -e GPU_ENABLED=true \
  -e LOG_LEVEL=INFO \
  -v /app/models:/app/models \
  -v $(pwd)/logs:/logs \
  ahfl-batch-processor:d4 \
  python services/batch-processor/batch.py \
    --source s3://uat_raw/ \
    --log-to-db

# Monitor progress
docker logs -f ahfl-batch-processor-prod | grep -E "COMPLETED|FAILED|ERROR"
```

---

## 7. TROUBLESHOOTING

### GPU Not Being Used
```bash
# Check GPU device in logs
docker logs ahfl-masking-engine-d4 | grep device

# If shows "cpu", GPU_ENABLED env var not set or false
# Verify: docker inspect ahfl-masking-engine-d4 | grep GPU_ENABLED
```

### S3 Upload Still Using Staging
```bash
# Check logs for old pattern (staging copy/delete)
docker logs ahfl-batch-processor-test | grep "_staging"

# If found: patch D4.3 not applied — check GPU_MASTER_SYNC.py output
```

### Slow OCR (> 5s)
```bash
# Check if running on CPU
docker logs ahfl-batch-processor-test | grep -i "cpu\|inference"

# If GPU inference time > 2s: CUDA memory pressure
nvidia-smi  # Check utilization
```

### DynamoDB Write Failed
```bash
# Check AWS credentials
docker exec ahfl-batch-processor-test env | grep AWS_

# Test connection
docker exec ahfl-batch-processor-test python -c \
  "import boto3; dynamodb = boto3.resource('dynamodb', region_name='us-east-1'); \
   print(list(dynamodb.tables.all()))"
```

---

## 8. ROLLBACK (if critical issues)

```bash
# Stop D4 containers
docker stop ahfl-batch-processor-prod ahfl-masking-engine-d4

# Restore from main branch
cd /data-disk/ahfl_deploy_gpu/
git checkout main -- core/ocr/paddle.py services/batch-processor/

# Rebuild with main code
docker build -t ahfl-batch-processor:main services/batch-processor/
docker build -t ahfl-masking-engine:main services/masking-engine/

# Restart with main
docker run -d --name ahfl-batch-processor --gpus all ... ahfl-batch-processor:main
docker run -d --name ahfl-masking-engine --gpus all ... ahfl-masking-engine:main
```

---

## SUCCESS CRITERIA

✅ All checks pass:
- [ ] GPU memory allocated (nvidia-smi shows > 0MB)
- [ ] Logs show "gpu:0" device (not CPU)
- [ ] Single image processes < 5s (GPU) vs > 10s (CPU)
- [ ] DynamoDB record created with status=COMPLETED
- [ ] S3 upload direct (no _staging artifacts)
- [ ] Masked output file exists in uat_masked with proper black boxes
- [ ] Logging records capture all pipeline stages
