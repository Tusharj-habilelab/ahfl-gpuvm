# Scripts — Role Guide

## `scripts/` root (one-time setup)

| File | Role |
|------|------|
| `setup_and_first_inference.py` | One-time GPU server setup — verifies model files, initializes PaddleOCR (~200MB download), runs full test pipeline on sample image. Run once after first deploy. |
| `inspect_yolo_models.py` | Model audit — loads all 4 YOLO `.pt` files, runs dummy inference, dumps architecture + class names to `reporting/model_metadata_report.txt`. Use when debugging model issues. |
| `create_dynamo_table.py` | One-time DB setup — creates DynamoDB table with correct schema (PK/SK + GSI1 index). Run once before first batch job. |

---

## `scripts/operational/` (day-to-day ops)

| File | Role |
|------|------|
| `dms_push.py` | **Final pipeline step** — pushes masked files to AHFL's TCS DMS API. Takes a CSV input with file metadata. **Currently a stub — needs porting from 1.0.** |
| `logs.py` | Stats reporting — scans DynamoDB for a date range, outputs CSV with masking counts, error counts, Aadhaar detections. |
| `validate_config.py` | Pre-flight checker — verifies GPU, S3 buckets, DynamoDB table, model files, and PaddleOCR before running a batch. |
| `creates_batches.py` | Data prep — splits a raw input folder into N sub-batches by application number. Run before feeding data to batch processor. |
| `count_total_applications.py` | Audit tool — counts unique applications and files in a folder, outputs CSV. Use to verify input data before processing. |
| `count_total_application.py` | Simpler version of above — prints to terminal, no CSV output. |
| `log_file_paths.py` | Path inventory — recursively lists all file paths in a folder to a CSV. Used to prepare `file_paths.csv` for `copy_files.py`. |
| `copy_files.py` | File mover — reads source/destination pairs from `file_paths.csv` and copies files. Used to stage files between locations. |
| `checklogs.sh` | **Stale** — was a wrapper to run export + count scripts across 15 MySQL batch dirs. No longer valid for DynamoDB workflow. |

---

## `scripts/reporting/` (post-processing & reporting)

| File | Role |
|------|------|
| `export_logs.py` | DynamoDB → CSV export — pulls all records from DynamoDB to a local CSV. Input for `main.py`. |
| `main.py` | Log processor — strips local path prefix, extracts file_name/ATTACH_ID/APPLICATION_NO, aggregates per file_path. Produces `processed_logs/`. **Hardcoded path prefix needs to become env var.** |
| `merge_csvs.py` | CSV combiner — merges multiple CSVs from `processed_logs/` into one `merged_logs.csv`. |
| `merge_metadata.py` | Metadata merger — merges all `.xlsx` metadata files into `Metadata_FY2526.csv`. |
| `mapping.py` | Final join — left-joins metadata CSV with logs CSV on `ATTACH_ID`, produces `final_joined_output.csv` for AHFL delivery. |
| `copy_files.py` | Copies files by source/destination CSV. Same as operational version. |

---

## Typical Run Order

```
SETUP (once):
  create_dynamo_table.py → setup_and_first_inference.py

BEFORE EACH BATCH:
  validate_config.py → creates_batches.py → batch processor

AFTER EACH BATCH:
  logs.py (stats) → dms_push.py (deliver to DMS)

FOR MONTHLY REPORT:
  export_logs.py → main.py → merge_csvs.py → merge_metadata.py → mapping.py
```

---

## Pending Fixes

| File | Issue |
|------|-------|
| `operational/dms_push.py` | Port full 1.0 implementation from `AHFL-Masking/server/scripts/dms_script.py`; move all credentials to env vars |
| `reporting/main.py` | Replace hardcoded `/opt/Aadhaar_Masking_Project/Aadhaar_Masking_WIP/` with `MASKED_FILES_DIR` env var |
| `operational/checklogs.sh` | Rewrite for DynamoDB workflow or retire — `export_logs.py` already covers its function |
