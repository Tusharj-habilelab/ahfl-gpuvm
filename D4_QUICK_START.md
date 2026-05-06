# D4 GPU DEPLOYMENT — QUICK START

## Files Created
1. **D4_PATCHES_FOR_GPU.py** — Patch code to append to GPU_MASTER_SYNC.py
2. **D4_GPU_DEPLOYMENT_TEST.md** — Complete deployment + testing workflow
3. **GPU_DEPLOYMENT_CHANGES.md** — High-level change summary

---

## EXECUTION STEPS (On GPU Server)

### Phase 1: Apply Patches (5 minutes)
```bash
cd /data-disk/ahfl_deploy_gpu/

# Append D4 patches to GPU_MASTER_SYNC.py (line 651, before REPORT section)
# Copy from D4_PATCHES_FOR_GPU.py (3 patch blocks only)

# Run sync
python3 GPU_MASTER_SYNC.py
# Expected: Applied: 3 | Failed: 0
```

### Phase 2: Rebuild Docker (10 minutes)
```bash
docker build -t ahfl-batch-processor:d4 services/batch-processor/
docker build -t ahfl-masking-engine:d4 services/masking-engine/
```

### Phase 3: Dry Run Test (5 minutes)
```bash
# Start masking engine
docker run -d --name ahfl-masking-engine-d4 --gpus all \
  -e GPU_ENABLED=true -e LOG_LEVEL=DEBUG \
  -v /app/models:/app/models -p 8001:8001 \
  ahfl-masking-engine:d4

# Dry run (no S3 uploads)
docker run --rm --gpus all --name ahfl-batch-processor-dryrun \
  -e GPU_ENABLED=true -e LOG_LEVEL=DEBUG \
  -e RAW_BUCKET=uat_raw -e MASKED_BUCKET=uat_masked \
  -v /app/models:/app/models \
  ahfl-batch-processor:d4 \
  python services/batch-processor/batch.py --source s3://uat_raw/test_sample/ --dry-run

# Check: No S3 uploads, no DynamoDB writes
```

### Phase 4: Single Image Test (15 minutes)
```bash
# Upload test image to S3
aws s3 cp ~/test_aadhaar.jpg s3://uat_raw/test_sample/test_aadhaar.jpg

# Process it
docker run --rm --gpus all --name ahfl-batch-processor-test \
  -e GPU_ENABLED=true -e LOG_LEVEL=DEBUG \
  -e RAW_BUCKET=uat_raw -e MASKED_BUCKET=uat_masked \
  -e TABLE_NAME=ahfl_processed_data \
  -v /app/models:/app/models \
  ahfl-batch-processor:d4 \
  python services/batch-processor/batch.py --source s3://uat_raw/test_sample/test_aadhaar.jpg
```

### Phase 5: Verify (10 minutes)
**GPU:**
```bash
nvidia-smi  # Check: both containers using GPU, < 4GB mem
docker logs ahfl-masking-engine-d4 | grep gpu:0  # Check: GPU device
docker logs ahfl-batch-processor-test | grep "Uploaded"  # Check: direct upload (no _staging)
```

**Database:**
```bash
aws dynamodb get-item --table-name ahfl_processed_data \
  --key '{"s3_key": {"S": "s3://uat_raw/test_sample/test_aadhaar.jpg"}}' \
  --region us-east-1
# Expected: status=COMPLETED, masked_s3_key populated
```

**Logging:**
```bash
docker logs ahfl-batch-processor-test | grep -E "OCR|YOLO|inference"
# Expected: inference times < 2s (GPU speed)
```

**Masked Output:**
```bash
aws s3 cp s3://uat_masked/test_sample/test_aadhaar.jpg ~/masked_aadhaar.jpg
# Verify: file exists, has black boxes on sensitive areas
```

---

## SUCCESS = All Green ✅
- [ ] Patches applied (GPU_MASTER_SYNC output)
- [ ] Docker images built
- [ ] Dry run: no uploads, no DB writes
- [ ] Single image: < 5s processing (GPU)
- [ ] DynamoDB: record created, status=COMPLETED
- [ ] S3: direct upload (no _staging keys)
- [ ] Logs: GPU device logged, fast inference
- [ ] Output: masked image with black boxes

---

## IF ISSUES
Detailed troubleshooting: See D4_GPU_DEPLOYMENT_TEST.md Section 7
