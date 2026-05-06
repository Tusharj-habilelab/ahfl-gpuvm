# GPU Server Sync — Pending Changes

Files changed locally that must be copied to the GPU server before the next run.
Update this file after each sync.

## 🚨 CRITICAL SECURITY FIXES (C1, C2, C3) — 2026-05-02

**Status**: Implemented locally. Ready to sync to GPU server immediately.

**Summary**: Three CRITICAL form-lane security issues fixed:

| Issue | Root Cause | Fix | Impact |
|-------|-----------|-----|--------|
| **C1** | `is_pan_card()` bare "PAN" substring matches applicant names (Pankaj/Pandey) | Multi-signal approach: require 2+ signals (INCOME TAX DEPARTMENT, PERMANENT ACCOUNT, regex, word-boundary) | Documents with names containing "Pan" prefix now correctly identified as forms, not skipped as PAN cards |
| **C2** | `cersai_found` returns empty list but report shows skipped=False → zero masking applied silently | Add logging: "C2 FIX: CERSAI keyword detected — skipping masking" for audit trail | Masking decisions now explicitly logged; CERSAI detection visible in logs |
| **C3** | `aadhar_found` gate blocks ALL number masking if OCR corrupts "aadhaar"/"aadhar" → even valid Aadhaar numbers skipped (form lane only) | Add unconditional Verhoeff safety pass at end of find_aadhaar_patterns(): any 12-digit Verhoeff-valid number masked regardless of keyword match | Form lane documents with corrupted Aadhaar keyword still have numbers masked via Verhoeff validation |

**Files Modified**:
- `core/classifiers.py` - C1 fix: is_pan_card() multi-signal logic
- `core/ocr/masking.py` - C2 fix: cersai logging + C3 fix: Verhoeff safety pass
- `GPU_MASTER_SYNC.py` - PATCH 10, 11, 12 added for all three fixes

**Deployment Instructions**:
1. Copy updated GPU_MASTER_SYNC.py to `/data-disk/ahfl_deploy_gpu/`
2. Run: `cd /data-disk/ahfl_deploy_gpu && python GPU_MASTER_SYNC.py`
3. Verify all 3 patches applied (PATCH 10, 11, 12 in output)
4. Rebuild Docker: `docker compose --profile batch build`
5. Test with form documents that have applicant names with "Pan" prefix + corrupted Aadhaar keywords

---

## Pending (not yet on GPU server)

### Router + Lane-Based Pipeline Flow (2026-05-02) — IMPLEMENTED

**Status**: Completed locally. Ready to sync to GPU server.

**Summary**: Both missing items are now done:
- lane refactor in `core/pipeline.py`
- DB schema + batch DB writes update

Also completed: centralized threshold/config values so key paths read from `core/config.py`.

**Implementation plan**: `/memories/session/plan.md`

**Completed changes**:

| File                                    | Change                                                                                                                                                                                                                                                                                                                                                                                                                        | Date       |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `core/router.py` (new)                 | New module: `classify_document_lane()` returns `form | card | uncertain` based on OCR-lite keyword matching + text density + Aadhaar cues; includes `_normalize_text()`, `_contains_card_signals()`, `_contains_form_signals()`, `_contains_skip_signals()`                                                                                                                                          | 2026-05-02 |
| `core/ocr/paddle.py`                   | Added `run_ocr_lite_for_routing()` and moved routing OCR limits to config (`ROUTER_OCR_LITE_MAX_SIDE`, `ROUTER_OCR_LITE_MAX_TOKENS`); moved OCR resize max side to config (`PADDLE_OCR_MAX_SIDE`)                                                                                                                                                                                                                            | 2026-05-02 |
| `core/config.py`                       | Added router/composite thresholds plus central constants for batch limits and path skips: `ROUTER_*`, `ORIENTATION_TARGET_THRESHOLD`, `ORIENTATION_STRONG_THRESHOLD`, `MAX_PDF_PAGES`, `PDF_CHUNK_SIZE`, `MAX_S3_FILE_SIZE`, `STALE_PROCESSING_HOURS`, `BATCH_PATH_SKIP_KEYWORDS`, PVC thresholds                                                                                                                          | 2026-05-02 |
| `core/aadhaar_gate.py`                 | Modified `run_full_gate_scoring()` to extract and return `best_number_conf` and `best_qr_conf` from merged detections (best.pt model evidence) in gate_result dict                                                                                                                                                                                                                                                           | 2026-05-02 |
| `core/utils/angle_detector.py`         | Replaced with clean implementation; composite early exit now config-driven (`ORIENTATION_STRONG_THRESHOLD` + `ORIENTATION_TARGET_THRESHOLD`)                                                                                                                                                                                                                                                                                | 2026-05-02 |
| `core/classifiers.py`                  | Added `normalize_aadhaar_keyword()` and made PVC detection thresholds config-driven (`PVC_PERSON_CONFIDENCE_THRESHOLD`, `PVC_MAX_ROTATIONS`)                                                                                                                                                                                                                                                                                 | 2026-05-02 |
| `core/pipeline.py`                     | Full lane-based refactor implemented: router call + `_process_form_lane` and card-like lane path; verification now runs before YOLO/PVC masking; added `lane_chosen`, `final_winning_angle`, `card_detected`, `aadhaar_verified`, `pan_found`, `mask_counts` in report                                                                                                                                                     | 2026-05-02 |
| `core/db/database.py`                  | Added DB schema defaults + helper (`DEFAULT_MASK_COUNTS`, `build_default_record`) with new fields: `lane_chosen`, `orientation_hint_angle`, `final_winning_angle`, `skip_reason`, `card_detected`, `aadhaar_verified`, `pan_found`, `mask_counts`                                                                                                                                                                        | 2026-05-02 |
| `services/batch-processor/batch.py`    | Uses config constants for thresholds/limits; pending/completed DB writes updated to include new schema fields and nested `mask_counts` while preserving old flat counters for compatibility                                                                                                                                                                                                                                   | 2026-05-02 |
| `services/masking-engine/engine.py`    | Removed hardcoded runtime thresholds in key paths: now uses config for GPU memory fraction and PDF chunk size                                                                                                                                                                                                                                                                                                               | 2026-05-02 |

**Remaining follow-up (optional)**:
- Additional deep sweep can migrate every legacy heuristic threshold in `core/ocr/masking.py` to config as a second pass.

---

| File                                    | Change                                                                                                                                                                                                                                                                                                                                                                                                                        | Date       |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `services/batch-processor/batch.py`   | `_get_skip_paths()` — replaced full table scan with GSI1 query; added path keyword skip filter (12 keywords); `MAX_S3_FILE_SIZE` changed from 100MB to 15MB; `validate_required_env_vars()` call added at startup; ZIP extraction functions `_unzip()` and `_extract_path()` added (S3 mode: extract-only; local mode: re-zip); `_extract_path(source_dir, s3_mode=True)` call added before file processing loop | 2026-05-01 |
| `docker-compose.yml`                  | `paddleocr_cache` named volume → `/ahfl-models/.paddlex` bind mount; dropped `masked_output` + `/ahfl-source-data` from batch-processor                                                                                                                                                                                                                                                                              | 2026-05-01 |
| `services/batch-processor/Dockerfile` | `CMD` → `["--s3"]`; `VOLUME` → `["/app/models"]` only                                                                                                                                                                                                                                                                                                                                                               | 2026-05-01 |
| `scripts/reporting/main.py`           | `prefix_to_remove` — removed hardcoded `/opt/...` path; now reads `RAW_BUCKET` env var and strips `s3://<RAW_BUCKET>/` prefix                                                                                                                                                                                                                                                                                        | 2026-05-01 |
| `core/config.py`                      | Added `validate_required_env_vars()`; **MAX_FILE_SIZE default 10MB → 15MB** (was inconsistent with batch.py)                                                                                                                                                                                                                                                                                                         | 2026-05-01 |
| `core/utils/file_utils.py`            | `validate_file_size()` default changed hardcoded 10MB → reads from `core.config.MAX_FILE_SIZE` (15MB)                                                                                                                                                                                                                                                                                                                    | 2026-05-01 |
| `services/api-gateway/main.py`        | `MAX_UPLOAD` hardcoded 10MB → reads from `core.config.MAX_FILE_SIZE` (15MB)                                                                                                                                                                                                                                                                                                                                              | 2026-05-01 |
| `services/masking-engine/engine.py`   | MAX_FILE_SIZE now reads from core.config; file size check moved before save (Content-Length, 413 status); PDF processing now chunks 10 pages at a time;`validate_required_env_vars()` call added to startup event                                                                                                                                                                                                           | 2026-05-01 |
| `core/ocr/ocr_adapter.py`             | Added logging import and logger — exception handlers now log failures instead of silent skip                                                                                                                                                                                                                                                                                                                                 | 2026-05-01 |
| `core/classifiers.py`                 | Added logging import and logger;`mask_pvc_aadhaar()` refactored to return (image, stats_dict) with pvc_cards_processed/masked counts + debug logging; `_get_person_model()` added for yolov8n lazy-load                                                                                                                                                                                                                   | 2026-05-01 |
| `core/pipeline.py`                    | Added `mask_pvc_aadhaar` import; integrated PVC masking call after mask_yolo_detections (stage 2a.5); pvc_stats merged into final report using `**pvc_stats`; pvc_stats initialized with default keys                                                                                                                                                                                                                     | 2026-05-01 |

## Sync steps (on GPU server after copying files)

```bash
# If Dockerfile changed — rebuild required
docker compose --profile batch build batch-processor

# Then run
docker compose --profile batch run batch-processor
```

## Already synced

_(move rows here after confirming on GPU server)_
