# Diff: AHFL-Masking 1.0 (bulk.py) vs 1.1 (batch.py)

## Context

1.0 used: EasyOCR + MySQL + local file system + manual batch dirs
1.1 uses: PaddleOCR + DynamoDB + S3 + Docker services

---

## Core Pipeline Differences

| Feature | 1.0 (`bulk.py`) | 1.1 (`batch.py`) |
|---------|----------------|-----------------|
| OCR engine | EasyOCR | PaddleOCR (GPU) |
| Database | MySQL | DynamoDB |
| Storage | Local filesystem (`/opt/...`) | AWS S3 |
| Serving | Flask server | FastAPI microservices |
| GPU | Optional | Required |
| Batching | Manual folder splits | S3-based continuous processing |
| Skip tracking | File keyword filter (`to_skip_file`) + in-memory set | DynamoDB query (`_get_skip_paths`) |

---

## Features in 1.0 Missing from 1.1

| Feature | 1.0 Location | 1.1 Status | Action |
|---------|-------------|------------|--------|
| DMS push | `server/scripts/dms_script.py` | `scripts/operational/dms_push.py` is a stub (`NotImplementedError`) | **Port 1.0 implementation, move credentials to env vars** |
| Skip-keyword filter | `bulk.py:to_skip_file()` — 11 keywords: `property, credit, bureau, sampling, screening, banking, epfo, tereport, estimate, location, sketch, cersai` | Not in `batch.py` | Confirm with AHFL if still needed |
| ZIP/RAR archive extraction | `bulk.py:extractPath()` | Not implemented | Confirm if S3 bucket contains archives |
| PVC Aadhaar masking | `bulk.py:mask_pvc_aadhaar()` using `yolov8n.pt` (person detection) | `MODEL_YOLO_N` env var exists but never used in code | Confirm if PVC cards are in scope |

---

## 1.0 `server/scripts/` → 1.1 `scripts/operational/` Mapping

| 1.0 File | 1.1 File | Status |
|----------|----------|--------|
| `dms_script.py` | `dms_push.py` | **Stub — needs porting** |
| `count_total_application.py` | `count_total_application.py` | Identical |
| `count_total_applications.py` | `count_total_applications.py` | Identical |
| `log_file_paths.py` | `log_file_paths.py` | Identical |
| `creates_batches.py` | `creates_batches.py` | Identical |
| `copy_files.py` | `copy_files.py` | Identical |
| `logs.py` (MySQL, 15 hardcoded tables) | `logs.py` (DynamoDB, date-range scan) | Migrated correctly |
| `checklogs.sh` (15 MySQL batch dirs) | `checklogs.sh` | **Stale** — references `/data/batches/N/` dirs that don't exist on GPU server |

---

## 1.0 `server/report/` → 1.1 `scripts/reporting/` Mapping

| 1.0 File | 1.1 File | Status |
|----------|----------|--------|
| `main.py` | `main.py` | **Hardcoded** `/opt/Aadhaar_Masking_Project/Aadhaar_Masking_WIP/` prefix — must be env var |
| `merge_metadata.py` | `merge_metadata.py` | Identical |
| `merge_csvs.py` | `merge_csvs.py` | Identical |
| `mapping.py` | `mapping.py` | Identical |
| `copy_files.py` | `copy_files.py` | Identical |
| *(none)* | `export_logs.py` | New in 1.1 — correctly DynamoDB-based |

---

## Role of Every Script File

### `scripts/` root (one-time setup)

| File | Role |
|------|------|
| `setup_and_first_inference.py` | One-time GPU server setup — verifies models, initializes PaddleOCR (~200MB download), runs test pipeline. Run once after first deploy. |
| `inspect_yolo_models.py` | Loads all 4 YOLO `.pt` files, dumps architecture + class names to `reporting/model_metadata_report.txt`. Use when debugging model issues. |
| `create_dynamo_table.py` | Creates DynamoDB table with correct schema (PK/SK + GSI1). Run once before first batch job. |

### `scripts/operational/`

| File | Role |
|------|------|
| `dms_push.py` | Final pipeline step — pushes masked files to AHFL's TCS DMS API. Takes CSV input. **Stub — needs port.** |
| `logs.py` | Scans DynamoDB for date range, outputs masking stats CSV. |
| `validate_config.py` | Pre-flight — checks GPU, S3 buckets, DynamoDB table, model files, PaddleOCR before batch run. |
| `creates_batches.py` | Splits raw input folder into N sub-batches by application number. Run before feeding batch processor. |
| `count_total_applications.py` | Counts unique applications + files in folder, outputs CSV. Verify input data before processing. |
| `count_total_application.py` | Same but prints to terminal only (no CSV). |
| `log_file_paths.py` | Recursively lists all file paths in folder to CSV. Prepares `file_paths.csv` for `copy_files.py`. |
| `copy_files.py` | Reads source/destination pairs from `file_paths.csv`, copies files. |
| `checklogs.sh` | **Stale** — MySQL-era wrapper. Retire; `export_logs.py` covers its function. |

### `scripts/reporting/`

| File | Role |
|------|------|
| `export_logs.py` | DynamoDB → CSV export. Input for `main.py`. |
| `main.py` | Strips path prefix, extracts file_name/ATTACH_ID/APPLICATION_NO, aggregates per file_path → `processed_logs/`. **Needs env var fix.** |
| `merge_csvs.py` | Merges CSVs from `processed_logs/` into `merged_logs.csv`. |
| `merge_metadata.py` | Merges all `.xlsx` metadata files into `Metadata_FY2526.csv`. |
| `mapping.py` | Left-joins metadata + logs on `ATTACH_ID` → `final_joined_output.csv` for AHFL delivery. |
| `copy_files.py` | Copies files by source/destination CSV. |

---

## Typical Run Order

```
SETUP (once):
  create_dynamo_table.py → setup_and_first_inference.py

BEFORE EACH BATCH:
  validate_config.py → creates_batches.py → batch processor (Docker)

AFTER EACH BATCH:
  logs.py → dms_push.py

MONTHLY REPORT:
  export_logs.py → main.py → merge_csvs.py → merge_metadata.py → mapping.py
```

---

## Pending Fixes (Priority Order)

| Priority | File | Fix |
|----------|------|-----|
| HIGH | `operational/dms_push.py` | Port 1.0 `dms_script.py`; move `auth_token`, `JSESSIONID`, `URL`, `USER_ID`, `TENANT_ID`, `MASKED_FILES_DIR` to env vars |
| HIGH | `reporting/main.py` | Replace `/opt/Aadhaar_Masking_Project/Aadhaar_Masking_WIP/` with `MASKED_FILES_DIR` env var |
| LOW | `operational/checklogs.sh` | Retire — replace with `export_logs.py` call |
| CONFIRM | `batch.py` | Add `to_skip_file()` keyword list (11 keywords from 1.0)? |
| CONFIRM | `batch.py` | Add ZIP/RAR extraction support? |
| CONFIRM | `core/aadhaar_gate.py` | Add PVC Aadhaar masking via `yolov8n.pt`? |

---

## DMS Script — Credential Env Vars Needed

1.0 hardcoded values that must move to `.env` / environment:

| Env Var | Description |
|---------|-------------|
| `DMS_URL` | TCS DMS API endpoint |
| `DMS_AUTH_TOKEN` | URL-encoded auth token for `auth_token` header |
| `DMS_JSESSIONID` | Session cookie value |
| `DMS_USER_ID` | Numeric user ID |
| `DMS_TENANT_ID` | Numeric tenant ID |
| `MASKED_FILES_DIR` | Base path where masked files are stored (replaces hardcoded `/opt/...` prefix) |
