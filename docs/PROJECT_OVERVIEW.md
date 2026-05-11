# AHFL-Masking 1.1 — Project Overview

A microservices re-architecture of the AHFL Aadhaar masking platform, GPU-accelerated for high-throughput document KYC processing.

---

## 1. What the system does

Automatically detects and masks sensitive identity information in customer documents:

- **Aadhaar numbers** — masks 8 of the 12 digits (first 8 hidden, last 4 visible)
- **QR codes** — masks Aadhaar QR codes (scoped to Aadhaar cards only; never on PAN cards)
- **PAN cards** — detected and routed away from Aadhaar masking logic
- **Forms** — handles loan-application forms with the same OCR/masking pipeline

Inputs: JPG, JPEG, PNG, PDF (up to 10 MB).
Outputs: masked file + structured JSON report (per-page masking status).

---

## 2. Architecture

The 1.0 monolith was split into **3 microservices** sharing a single `core/` library (zero code duplication):

```
AHFL-Masking 1.1/
├── core/                     # Shared library — single source of truth
│   ├── pipeline.py           # process_image() — the masking pipeline entrypoint
│   ├── aadhaar_gate.py       # Aadhaar confidence gate + scoring
│   ├── classifiers.py        # Aadhaar-side detector + PAN-card detector
│   ├── spatial.py            # Bounding-box / coordinate utilities
│   ├── ocr/
│   │   ├── paddle.py         # PaddleOCR adapter (GPU)
│   │   ├── ocr_adapter.py    # Higher-level OCR interface
│   │   └── masking.py        # Digit-masking primitives
│   ├── models/
│   │   └── yolo_runner.py    # YOLO load/inference wrapper
│   ├── db/
│   │   ├── database.py       # MySQL + DynamoDB connection helpers
│   │   └── log_writer.py     # Bulk log writer for batch runs
│   ├── utils/
│   │   ├── file_utils.py     # Format conversion, PDF handling
│   │   └── counts.py         # Page/file counting
│   └── config.py             # Centralized config — single source of truth
├── services/
│   ├── api-gateway/          # FastAPI — auth + routing (port 8000)
│   ├── masking-engine/       # FastAPI — masking pipeline (port 8001)
│   └── batch-processor/      # One-shot CLI job — bulk S3/folder processing
├── scripts/
│   └── operational/          # DMS push, config validation, etc.
└── docs/                     # Project documentation
```

### Service responsibilities

| Service | Type | Port | Role |
|---|---|---|---|
| **api-gateway** | FastAPI service | 8000 | Public-facing. API-key auth, file validation, proxies to masking-engine. |
| **masking-engine** | FastAPI service | 8001 | Core inference. Long-running; pre-warms YOLO + PaddleOCR on startup. |
| **batch-processor** | CLI job | n/a | Bulk processing from local folder or S3 source. Writes status to DynamoDB. |

### Why this split

- **api-gateway** stays light — no ML deps, fast cold start, easy to replicate behind a load balancer.
- **masking-engine** holds all GPU/ML deps; expensive to start, so it's a long-running service with model warmup.
- **batch-processor** runs as a one-shot job (Kubernetes Job / ECS Task) for large overnight runs.

---

## 3. The masking pipeline (`core/pipeline.py`)

End-to-end flow for one image:

```
Input image
   │
   ▼
[1] Pre-check: PP-LCNet_x1_0_doc_ori orientation classifier
   │      (runs for BOTH card and form paths — early-exit if confident)
   ▼
[2] Path split — card vs form
   │
   ├── Card path ──────────────────────────────────────────┐
   │     [3a] Aadhaar-side detector (front_back_detect.pt) │
   │     [4a] Aadhaar gate scoring (confidence formula)    │
   │          ├─ PAN-card check (only here, not on forms)  │
   │          └─ Aadhaar fallback if gate fails            │
   │     [5a] YOLO main.pt → Aadhaar bbox on full image    │
   │     [6a] YOLO best.pt → Number bbox on cropped Aadhaar│
   │     [7a] PaddleOCR on Aadhaar bbox crop               │
   │     [8a] Validate digits → mask 8 of 12 digits        │
   │     [9a] QR detection + masking (Aadhaar only)        │
   │
   └── Form path ──────────────────────────────────────────┐
         [3b] Cardinal + diagonal angle sweep              │
              (uses PP-LCNet for hard correction)          │
         [4b] Keyword-based form verification              │
         [5b] PaddleOCR full-page                          │
         [6b] Aadhaar number pattern detection             │
         [7b] Mask matched digits                          │
   │
   ▼
Masked image + per-page report
```

### Key design decisions

| Decision | Detail |
|---|---|
| **PP-LCNet roles** | Pre-check on both paths; hard orientation correction only on form path. |
| **best.pt scope** | Runs on *cropped* Aadhaar bbox (from main.pt), not on the full image. |
| **PAN-card check scope** | Only on Aadhaar card path — forms never trigger it. |
| **Digit masking** | 8 of 12 digits. OCR validates the digits before masking is applied (fallback if invalid). |
| **QR detection scope** | Restricted to Aadhaar cards. Never runs on PAN or forms. |
| **Skip mechanisms** | Two independent: (a) path-based via DynamoDB-listed numeric application/attach-IDs in S3 keys, (b) content-based via skip keywords. |
| **Form orientation** | Cardinal (0/90/180/270) + diagonal angles, gated by keyword verification. |

---

## 4. Models

Four YOLO/classifier models pre-loaded at `/ahfl-models` on the GPU host:

| Model | Path env var | Role |
|---|---|---|
| `main.pt` | `MODEL_MAIN` | Primary YOLO — Aadhaar bbox detection on full image |
| `best.pt` | `MODEL_BEST` | Secondary YOLO — number bbox on cropped Aadhaar |
| `front_back_detect.pt` | `MODEL_FRONT_BACK` | Aadhaar front/back classifier |
| `yolov8n.pt` | `MODEL_YOLO_N` | YOLOv8n base model |

Plus PaddleOCR (3.4.0): `det / rec / cls / doc_orientation` sub-models, pre-cached under `/app/models/paddleocr/`.

---

## 5. GPU stack

Both `masking-engine` and `batch-processor` use the same GPU foundation:

- **Base image:** `nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04`
- **PaddlePaddle:** `paddlepaddle-gpu==3.3.0` from `paddlepaddle.org.cn/.../cu121/` (cu121 ABI matches CUDA 12.2 host)
- **PyTorch:** `torch==2.1.2+cu121` + `torchvision==0.16.2+cu121`
- **PaddleOCR:** `3.4.0` (uses `use_textline_orientation=True` — `use_angle_cls` deprecated)
- **GPU env:** `CUDA_VISIBLE_DEVICES=0`, `TF_FORCE_GPU_ALLOW_GROWTH=true`

### Performance (T4 16GB vs 4-core CPU baseline)

| Workload | CPU | GPU | Speedup |
|---|---|---|---|
| Single image (JPG) | ~2.8s | ~0.3s | 9.3× |
| PDF (5 pages) | ~14s | ~1.5s | 9.3× |
| Throughput (img/min) | 21 | 198 | 9.4× |

---

## 6. API surface (api-gateway)

| Endpoint | Method | Description |
|---|---|---|
| `/aadhaar-masking` | POST | Upload file for masking (requires `apiKey` header) |
| `/masked/{filename}` | GET | Download masked file |
| `/` | GET | Gateway health check |

Internal (masking-engine, port 8001):

| Endpoint | Method | Description |
|---|---|---|
| `/mask` | POST | Direct engine call |
| `/health` | GET | Basic health + GPU status |
| `/health/detailed` | GET | CPU/memory + GPU device metrics |
| `/output/{filename}` | GET | Retrieve masked output by UUID |

---

## 7. Storage

- **MySQL** — legacy logging (1.0 carryover; some tables dead, e.g. `mysql-connector-python` was unused in masking-engine)
- **DynamoDB** — primary log table for batch runs; also stores skip-path list queried by `_get_skip_paths()`
- **S3** — batch source/destination in batch-processor S3 mode; preserves full key paths including numeric application/attach-ID segments
- **Local volumes** — `/app/models`, `/app/output`, `/app/source` (batch only)

---

## 8. Migration from 1.0

| 1.0 | 1.1 | Notes |
|---|---|---|
| Flask + wsgi.py | FastAPI + uvicorn | Async, OpenAPI built in |
| EasyOCR | PaddleOCR 3.4.0 | GPU acceleration, better Indic support |
| Monolith | 3 microservices + `core/` | Zero duplication |
| `process_image.py` | `services/masking-engine/engine.py` + `core/pipeline.py` | Logic moved to `core/` |
| `bulk.py` + `bulk1.py` + `bulk2.py` | `services/batch-processor/batch.py` | Single entry point |
| `paddleocr_integration/masking_functions.py` | `core/ocr/masking.py` | Shared |
| `utils/dbinit.py` | `core/db/database.py` | Shared |
| `detect_aadhaar_side.py` | `core/classifiers.py` | Shared |

---

## 9. Open items / known issues

- **`core/ocr/paddle.py`** — `use_gpu=` parameter fix not yet applied locally (still pending).
- **`batch.py preload_models()`** — duplicate GPU warmup block present (dead code).
- **`masking-engine/requirements.txt`** — still lists `mysql-connector-python` (dead dependency).
- **best.pt number-crop OCR enhancement** — deferred; OCR currently uses Aadhaar card bbox, not number-level crops.

---

## 10. Quick reference

| Need | Path |
|---|---|
| Run engine locally | `uvicorn engine:app --host 0.0.0.0 --port 8001` from `services/masking-engine/` |
| Run batch job | `python batch.py --source <dir> --dest <dir>` from `services/batch-processor/` |
| GPU deployment guide | `services/masking-engine/GPU_SETUP.md` |
| Pipeline change log | `docs/PIPELINE_CHANGES.md` |
| Pipeline flow detail | `docs/PIPELINE_FLOW.md` |
| Model spec | `docs/model-specification.md` |
