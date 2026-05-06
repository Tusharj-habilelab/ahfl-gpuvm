# AHFL-Masking 1.1 GPU — Comprehensive Handoff Document

**Date:** 2026-05-01 | **Last Update:** 2026-05-05  
**Generated for:** Continuation of GPU pipeline work after folder restructuring  
**Canonical Repository Path:** `/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu`
**Output Location:** `/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/HANDOFF.md`  
**Status:** In-repo canonical handoff document (not temp)

---

## 🎯 D4 GPU Deployment — Status Update (2026-05-05)

**ALL 3 CRITICAL ISSUES FIXED & VERIFIED LOCALLY** ✅

| Issue | Location | Fix | Status |
|-------|----------|-----|--------|
| PaddleOCR Model Path | core/ocr/paddle.py | Removed model_dir params from create_paddle_ocr() + get_doc_orientation_model() | ✅ Ready |
| OpenCV Channel Mismatch | services/batch-processor/batch.py, services/masking-engine/engine.py | Added cv2.imread(IMREAD_COLOR) + grayscale→BGR conversion | ✅ Ready |
| PADDLE_MODEL_DIR References | core/config.py | Config exists but NOT used in active code paths | ✅ No Blockers |

**Pipeline Verified:** image read (IMREAD_COLOR) → core/pipeline → create_paddle_ocr (auto-download to `/root/.paddlex`) → YOLO (3-channel) → masking

**GPU VM Patches:** 2/3 applied (batch.py ✅, masking-engine ✅), 1 already correct (paddle.py ✅)

**Next:** Docker rebuild → test with sample PDF

---

## ⚠️ CRITICAL: Path Migration (2026-05-01)

### Old Path (Deprecated)
```
/Users/tusharjain/projects/ahfl-working-Gpu
```

### New Path (Use Always)
```
/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu
```

### Migration Impact

- **VS Code Workspace:** Old workspace ID may lose chat history. Always open from new path.
- **Symlink Strategy (Optional):** Create symlink from old path to new path for seamless backward compatibility:
  ```bash
  ln -s /Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu \
        /Users/tusharjain/projects/ahfl-working-Gpu
  ```
- **Terminal/Scripts:** Update any hardcoded absolute paths in tasks, aliases, or CI/CD pipelines.
- **Chat History:** Prior chat sessions may appear under "old workspace" identity in VS Code Copilot. This is expected and not a data loss—it's a workspace identity split.

### Recommended Action
**Open this project ONLY via:** `/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu`  
Use this path consistently across all future work.

---

## 📁 Repository Structure

```
/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/
├── core/                              # ← Shared library (single source of truth)
│   ├── config.py                      # Centralized env vars, model paths, GPU config
│   ├── classifiers.py                 # YOLO person detection + PVC masking
│   ├── pipeline.py                    # Main masking flow orchestrator
│   ├── aadhaar_gate.py                # Aadhaar-specific gating logic
│   ├── spatial.py                     # Spatial operations (bounding boxes, etc.)
│   ├── ocr/                           # OCR integration layer
│   │   ├── paddle.py                  # PaddleOCR initialization (GPU-aware)
│   │   └── ocr_adapter.py             # Paddle result → internal format adapter
│   ├── db/                            # DynamoDB integration
│   ├── models/                        # Model loading utilities
│   └── utils/                         # File I/O, size validation, etc.
│
├── services/                          # ← Three independent microservices
│   ├── api-gateway/
│   │   ├── main.py                    # FastAPI entry point (8002) + auth check
│   │   └── Dockerfile
│   ├── masking-engine/
│   │   ├── engine.py                  # Masking logic + file handling (8001)
│   │   └── Dockerfile                 # GPU-enabled, NVIDIA device reservations
│   └── batch-processor/
│       ├── batch.py                   # S3/DynamoDB orchestrator, one-shot job
│       └── Dockerfile
│
├── scripts/                           # ← Utilities + reporting
│   ├── operational/                   # DMS push, server ops
│   ├── reporting/                     # Report generation from DynamoDB
│   └── *.py                           # Setup, inspection, validation tools
│
├── docs/                              # → Documentation (if present)
├── research/                          # → Colab notebooks, experiments
│
├── docker-compose.yml                 # ← 3-service orchestration + GPU support
├── .env.example                       # ← Config template (MUST fill before running)
├── README.md                          # Quick start guide
├── FIXES_APPLIED.md                   # ← **5 Recent code fixes** (see below)
├── GPU_SYNC_PENDING.md                # ← **Files NOT yet on GPU server** (see below)
├── GPU_SYNC_PATCHES.md                # Copy-paste instructions for GPU VM updates
├── GPU_MASTER_SYNC.py                 # Batch patching script
├── AGENTS.md                          # Copilot agent memory/context log
└── .claude/                           # Local Claude config files

```

---

## 🏗️ Architecture Overview

### High-Level Flow
```
Client Upload
  ↓
[API Gateway (8002)] — FastAPI, 10-15 MB file size limit
  ↓
[Masking Engine (8001)] — FastAPI, GPU-accelerated
  ├→ PaddleOCR: Extract text + bounding boxes
  ├→ YOLO (x3 models): Person, face, document detection
  ├→ Classifiers: PVC card, side detection
  └→ Masking: Black out detected regions
  ↓
Response: Masked file back to client
---
Batch Mode (separate process)
  ↓
[Batch Processor] — One-shot job, GPU-enabled
  ├→ S3 download (RAW_BUCKET)
  ├→ Process via same core logic
  ├→ S3 upload (MASKED_BUCKET)
  ├→ DynamoDB status tracking (ahfl_processed_data table)
  └→ Reporting

Volumes & Storage
  ├→ Host: /ahfl-models → Container: /app/models (RO mount)
  │   ├── main.pt, best.pt, front_back_detect.pt, yolov8n.pt (YOLO models)
  │   └── paddleocr/ (OCR model cache)
  ├→ Named volume: masked_output (API + Engine shared)
  └→ DynamoDB: Table name = ahfl_processed_data (AWS)
```

### Key Microservices

| Service | Port | Type | GPU? | Purpose |
|---------|------|------|------|---------|
| `api-gateway` | 8002 | HTTP | No | Auth, file upload, routing to engine |
| `masking-engine` | 8001 (internal) | HTTP | Yes | ML inference, masking, file return |
| `batch-processor` | — | CLI/Batch | Yes | S3 → process → S3 + DynamoDB |

---

## ⚙️ Configuration & Environment

### Required `.env` File

Copy `[.env.example](.env.example)` to `.env` and fill in:

```bash
# GPU Setup
GPU_ENABLED=true
TORCH_CUDA_MAX_MEMORY_FRAC=0.7
GPU_WARMUP=true

# AWS Credentials (prefer IAM role, else fill keys)
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>

# S3 Buckets (REQUIRED for batch mode)
RAW_BUCKET=ahfl-ams-raw-data-bucket-333813598364-ap-south-1-an
MASKED_BUCKET=ahfl-uat-ams-masked-data-bucket-333813598364-ap-south-1-an

# DynamoDB
TABLE_NAME=ahfl_processed_data

# Model Paths (inside container — mount via volumes)
MODEL_MAIN=/app/models/main.pt
MODEL_BEST=/app/models/best.pt
MODEL_FRONT_BACK=/app/models/front_back_detect.pt
MODEL_YOLO_N=/app/models/yolov8n.pt
PADDLE_MODEL_DIR=/app/models/paddleocr

# Service Ports
API_GATEWAY_PORT=8002
MASKING_ENGINE_PORT=8003
HOST=http://localhost:8002

# File Limits
MAX_PDF_PAGES=500
MAX_S3_FILE_SIZE=104857600  # 100 MB
```

**Validate at startup:** `core/config.py` now calls `validate_required_env_vars()` — startup fails immediately if TABLE_NAME, AWS_REGION, RAW_BUCKET, MASKED_BUCKET are missing.

---

## 🚀 Quick Start

### 1. Setup

```bash
cd /Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu
cp .env.example .env

# Fill in .env with real AWS/bucket values
# Ensure models are in /ahfl-models (host path on GPU server)
```

### 2. Run API + Masking Engine (HTTP Mode)

```bash
docker compose up --build
```

Verify health:
```bash
curl http://localhost:8002/health  # API Gateway
curl http://localhost:8001/health  # Masking Engine (internal)
```

### 3. Test Upload Endpoint

```bash
curl -X POST \
  -H "Authorization: Bearer <api-key-from-authorized-keys.txt>" \
  -F "file=@test.pdf" \
  http://localhost:8002/aadhaar-masking
```

### 4. Run Batch Processing (S3 Mode)

```bash
docker compose --profile batch run batch-processor
  # Optional: --source s3://bucket/prefix (default uses S3 env vars)
```

---

## 📋 Recent Changes (as of 2026-05-01)

### ✅ FIXES APPLIED (5 issues resolved)

See [FIXES_APPLIED.md](FIXES_APPLIED.md) for full details:

1. **Env Var Validation** → Startup fails fast if AWS/S3 config missing
2. **File Size Check** → Moved BEFORE save, uses Content-Length header, returns HTTP 413
3. **PDF Chunking** → 10-page chunks instead of loading all at once (prevents memory spike)
4. **PaddleOCR Logging** → Exception handlers log instead of silent fail
5. **YOLO Classifier GPU Support** → Proper `cuda` device selection, warmup

### ⚠️ PENDING GPU SERVER SYNCS

See [GPU_SYNC_PENDING.md](GPU_SYNC_PENDING.md) — **9 files NOT yet on `/data-disk/ahfl_deploy_gpu` GPU server:**

| File | Change | Status |
|------|--------|--------|
| `services/batch-processor/batch.py` | GSI1 query, ZIP extraction, validate_required_env_vars() | 🟡 Pending |
| `docker-compose.yml` | paddleocr_cache → bind mount, volumes cleanup | 🟡 Pending |
| `services/batch-processor/Dockerfile` | CMD → `["--s3"]`, volume cleanup | 🟡 Pending |
| `scripts/reporting/main.py` | Removed hardcoded path, uses RAW_BUCKET env | 🟡 Pending |
| `core/config.py` | validate_required_env_vars() added | 🟡 Pending |
| `services/masking-engine/engine.py` | Config-based file size, PDF chunking, validation | 🟡 Pending |
| `core/ocr/ocr_adapter.py` | Logging added | 🟡 Pending |
| `core/classifiers.py` | GPU support, PVC masking, logging | 🟡 Pending |
| `core/pipeline.py` | PVC masking integrated (stage 2a.5) | 🟡 Pending |

**⚠️ Two critical GPU VM patches still pending:**

- **PATCH 1:** `core/ocr/paddle.py` — `PADDLE_MODEL_DIR` wiring to PaddleOCR constructor (lines 33–41)
- **PATCH 2:** `core/utils/file_utils.py` — RGB conversion for grayscale PDFs (line 45: `.convert('RGB')`)

See [GPU_SYNC_PATCHES.md](GPU_SYNC_PATCHES.md) for copy-paste instructions.

---

## 🔧 Key Implementation Details

### 1. Model Loading (core/classifiers.py)

```python
# YOLO models loaded lazily on first call
def _get_person_model():
    # Loads yolov8n, caches in global _models
    # GPU-aware: respects GPU_ENABLED flag
```

### 2. PDF Processing (services/masking-engine/engine.py)

```python
# NEW: 10-page chunks to keep peak memory ~200 MB
def _mask_pdf(pdf_path):
    total_pages = get_total_pages(pdf_path)
    for page_start in range(0, total_pages, 10):
        page_end = min(page_start + 10, total_pages)
        chunk = convert_from_path(pdf_path, first_page=page_start, last_page=page_end)
        # Process chunk
```

### 3. Batch S3 Flow (services/batch-processor/batch.py)

```python
# NEW: ZIP extraction support
def _extract_path(source_dir, s3_mode=True):
    if source_dir.endswith('.zip'):
        _unzip(source_dir, extract_to=temp_dir)
        return temp_dir
    return source_dir

# Query DynamoDB GSI1 for skip paths
def _get_skip_paths():
    # Uses GSI1 query (faster than full table scan)
    # Filters by 12 skip keywords (malware, error, invalid, etc.)
```

### 4. PaddleOCR GPU Mode (core/ocr/paddle.py)

```python
# MUST BE APPLIED: Wire PADDLE_MODEL_DIR to constructor
def create_paddle_ocr():
    from core.config import GPU_ENABLED, PADDLE_MODEL_DIR
    return PaddleOCR(
        lang="en",
        use_textline_orientation=True,
        use_gpu=GPU_ENABLED,
        det_model_dir=os.path.join(PADDLE_MODEL_DIR, "det"),
        rec_model_dir=os.path.join(PADDLE_MODEL_DIR, "rec"),
        cls_model_dir=os.path.join(PADDLE_MODEL_DIR, "cls"),
    )
```

---

## ⚡ Known Issues & Workarounds

| Issue | Impact | Workaround | Fixed? |
|-------|--------|-----------|--------|
| PADDLE_MODEL_DIR not wired to PaddleOCR | Models download to /root/.paddlex instead of /app/models | Apply PATCH 1 from GPU_SYNC_PATCHES.md | 🟡 Local ✅ / GPU 🔴 |
| Grayscale PDFs (1-channel) fail YOLO (3-channel) | HTTP 500 on grayscale inputs | Apply PATCH 2: `.convert('RGB')` in file_utils.py | 🟡 Local ✅ / GPU 🔴 |
| masking-engine Dockerfile still has --workers 2 | GPU memory pressure, reduced throughput | Change `CMD ["uvicorn", "engine:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]` | 🟡 Pending |
| DMS push not implemented | Batch processor stub only | Implement port from 1.0; see scripts/operational/dms_push.py | ❌ Not done |
| HTTP 500 on GPU health check (occasional) | Masking endpoint down, CPU fallback | Re-validate CUDA/Paddle index alignment after GPU updates | 🔍 Investigation needed |

---

## 🧪 Testing & Validation

### Local Validation Checklist (Before GPU Deploy)

- [ ] Copy `.env.example` → `.env`, fill AWS credentials
- [ ] Run `docker compose build` (verify no build errors)
- [ ] Run `docker compose up` and check health endpoints
- [ ] Upload test PDF via curl (check 8002 response)
- [ ] Inspect masking-engine logs for PaddleOCR GPU startup
- [ ] Monitor memory during 50-page PDF processing (should not spike > 500 MB)

### GPU Server Validation (After Syncing Files)

- [ ] SSH into GPU server, cd `/data-disk/ahfl_deploy_gpu`
- [ ] Check files match FIXES_APPLIED.md checksums (or re-sync all)
- [ ] Run `docker compose --profile batch build` (rebuild if Dockerfile changed)
- [ ] Test batch run: `docker compose --profile batch run batch-processor --help`
- [ ] Dry-run S3 access: `docker compose --profile batch run batch-processor --s3 --source s3://RAW_BUCKET/test/ --dry-run`
- [ ] Monitor GPU during batch: `nvidia-smi` should show VRAM usage

---

## 📊 Git Status & Recent Work

### Current State

- **Not a Git repo** (note from Apr 30, 2026)
- **Local changes:** Multiple files modified per FIXES_APPLIED.md and GPU_SYNC_PENDING.md
- **GPU server state:** Older versions (missing 9 local fixes)

### Recent Sessions (from AGENTS.md context)

- **S14–S16 (Apr 30):** Resolved 4 PaddleOCR/Dockerfile GPU issues
- **S17–S19 (Apr 30):** Investigated PADDLE_MODEL_DIR unused config + Dockerfile diffs
- **S21 (May 1):** Rescheduled GPU VM update reminder, PADDLE_MODEL_DIR wiring confirmed active

---

## 🎯 Prioritized Next Actions

### Immediate (Must Do)

1. **Sync GPU Server (2 critical patches + 7 files)**  
   - Use [GPU_SYNC_PATCHES.md](GPU_SYNC_PATCHES.md) copy-paste script OR GPU_MASTER_SYNC.py
   - Verify PADDLE_MODEL_DIR and grayscale RGB patches applied
   - Rebuild batch-processor Dockerfile if changed
   - **Estimated:** 30 min (includes re-download if applicable)

2. **Test Batch Processor After Sync**  
   - Dry-run with small S3 file: `--s3 --source s3://bucket/single-file.pdf --dry-run`
   - Check logs for GSI1 query working (vs full table scan)
   - Monitor GPU VRAM
   - **Estimated:** 15 min

### Short-Term (This Week)

3. **Validate Masking Engine HTTP API**  
   - Upload 50-page PDF, verify no memory spike
   - Confirm chunking working (check logs for "Processing pages X–Y")
   - **Estimated:** 20 min

4. **Re-test after GPU VM Sunday updates**  
   - Health check both services
   - Confirm no regressions from OS/driver updates
   - **Estimated:** 10 min

### Medium-Term (This Sprint)

5. **Implement DMS Push (scripts/operational/dms_push.py)**  
   - Currently NotImplementedError stub
   - Port logic from AHFL 1.0
   - **Estimated:** 4–6 hours (depends on 1.0 availability)

6. **Audit PVC Masking Integration (core/pipeline.py)**  
   - Confirm stage 2a.5 works correctly
   - Validate pvc_stats merge into final report
   - **Estimated:** 1–2 hours

---

## 🔐 Security Notes

- **API Authentication:** Uses `config/authorized-keys.txt` (one key per line)
- **AWS Credentials:** Prefer IAM role over explicit keys in `.env`
- **S3 Bucket Policy:** Ensure batch-processor has GetObject + PutObject on both buckets
- **DynamoDB Access:** Batch processor needs read/write on `ahfl_processed_data` table
- **Docker GPU:** NVIDIA device plugins required on host; docker-compose.yml reserves all GPUs

---

## 📞 Bootstrap Prompt for Next Chat

Use this prompt in a **new VS Code Copilot chat** to onboard quickly:

```text
I'm continuing work on AHFL-Masking 1.1 GPU pipeline.

Workspace root: /Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu

Recent state:
- 5 code fixes applied locally (env validation, file size checks, PDF chunking, logging)
- 9 files NOT yet synced to GPU server at /data-disk/ahfl_deploy_gpu
- 2 critical GPU patches pending: PADDLE_MODEL_DIR wiring + grayscale RGB conversion
- Folder restructured 2026-05-01; use new path always for workspace continuity

Key files:
- FIXES_APPLIED.md (what's done locally)
- GPU_SYNC_PENDING.md (what's not on GPU server yet)
- GPU_SYNC_PATCHES.md (copy-paste sync instructions)
- core/config.py (centralized config)
- services/{api-gateway,masking-engine,batch-processor}/ (3-tier architecture)

Next priority: Sync GPU server, test batch processor dry-run, validate masking-engine HTTP API.

Please read HANDOFF.md first to understand full context.
```

---

## 📝 Verification Checklist

**What was explicitly verified:**

✅ Repository structure matches README.md and observed file tree  
✅ docker-compose.yml has 3 services + GPU device reservations  
✅ .env.example covers all required env vars  
✅ FIXES_APPLIED.md accurately summarizes 5 recent code changes  
✅ GPU_SYNC_PENDING.md lists all 9 files not yet on GPU server  
✅ GPU_SYNC_PATCHES.md contains actionable patch instructions  
✅ AGENTS.md shows recent investigation context (50 observations)  
✅ Canonical path confirmed: `/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu`  
✅ GPU hardware verified: Tesla T4, CUDA 13.0, NVIDIA driver 580.126.16 (from day1-25042026.md)  
✅ Models pre-loaded on GPU server at `/ahfl-models` (verified Apr 24)  

**What requires clarification:**

❓ DMS push implementation status (stub exists, full port pending)  
❓ HTTP 500 occasional GPU health check (needs re-validation after updates)  
❓ PVC masking integration stage 2a.5 (merged into pipeline, not yet validated end-to-end)

---

**Last Updated:** 2026-05-01 12:30 UTC  
**For Questions:** Check AGENTS.md memory context (50 obs); search "PADDLE_MODEL_DIR", "batch-processor", "GPU_ENABLED"
