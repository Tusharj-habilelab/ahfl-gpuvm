# AHFL Masking Pipeline — Change Log (v1.0 → v1.1)

## Overview

Rebuild of the masking pipeline from duplicated, inconsistent code in two services
to a unified `core/pipeline.py` that both services call.

---

## Architecture Change

| Aspect | v1.0 (Old) | v1.1 (New) |
|--------|-----------|------------|
| Pipeline location | Duplicated in `engine.py` + `batch.py` | Single `core/pipeline.py` |
| Entry point | `_mask_single_image()` / `_process_image()` | `process_image(image: np.ndarray)` |
| Orientation | Dead code (never called) | 8-angle sweep with detection reuse |
| YOLO models | main.pt + best.pt run independently | main.pt reused from orientation; best.pt fresh |
| QR masking | ALL QR codes masked | Only QR inside Aadhaar bbox (>=50% area overlap) |
| Number masking | 68% width hardcoded | `compute_digit_mask_region()` — 8/12 fraction |
| Aadhaar validation | Verhoeff only | Verhoeff + first-digit 2-9 + digit-repeat <=4 |
| PAN detection | None (PAN cards mismasked) | OCR keyword + regex `[A-Z]{5}[0-9]{4}[A-Z]` |
| SKIP_KEYWORDS | Batch only | Both services (shared from `core/config.py`) |
| Asyncio (batch) | 3 new event loops per image | Removed — synchronous + gc cleanup |
| GPU memory | No limit in batch | `TORCH_CUDA_MAX_MEMORY_FRAC=0.7` both services |
| GPU warmup | Engine only | Both services |
| Classifier I/O | Temp file write → read → delete | Direct numpy array to YOLO |
| Logging | `print()` statements | `logging.getLogger(__name__)` throughout |
| Shutdown | None (batch) | `threading.Event()` + SIGTERM/SIGINT handlers |

---

## File-Level Changes

### New Files

| File | Purpose |
|------|---------|
| `core/pipeline.py` | Unified masking pipeline — single source of truth |
| `core/spatial.py` | QR spatial containment logic (area overlap check) |
| `docs/PIPELINE_FLOW.md` | Architecture diagram + stage descriptions |
| `docs/PIPELINE_CHANGES.md` | This file |

### Modified Files

| File | What Changed |
|------|-------------|
| `core/config.py` | Added: GPU config, orientation config, batch config sections |
| `core/classifiers.py` | Removed disk I/O; added bounds clamping; added `is_pan_card()` |
| `core/ocr/masking.py` | Added `is_valid_aadhaar_number()`, `compute_digit_mask_region()`; replaced hardcoded 0.68; logging fixes |
| `core/utils/angle_detector.py` | Complete rewrite: `find_best_orientation()` with 8 angles + early exit |
| `core/__init__.py` | Added spatial + classifier exports |
| `core/ocr/__init__.py` | Added validation function exports |
| `core/utils/__init__.py` | Added angle detector exports |
| `services/masking-engine/engine.py` | Delegates to `core.pipeline.process_image()` |
| `services/batch-processor/batch.py` | Removed async; delegates to `core.pipeline.process_image()`; added GPU config + graceful shutdown |

---

## Function-Level Field Mapping

### Aadhaar Number Validation

| Check | Old | New | Status |
|-------|-----|-----|--------|
| Length = 12 digits | `verhoeff_validate()` checked | `is_valid_aadhaar_number()` checks | Done |
| First digit 2-9 | Missing | Added (UIDAI rule) | Done |
| Digit repeat <= 4 | In `verhoeff_validate()` | In `is_valid_aadhaar_number()` | Done |
| Verhoeff checksum | `verhoeff_validate()` | Called inside `is_valid_aadhaar_number()` | Done |

### Number Masking

| Field | Old | New | Status |
|-------|-----|-----|--------|
| Mask fraction | `0.68 * width` hardcoded | `compute_digit_mask_region()` = 8/12 = 0.667 | Done |
| Orientation handling | None (only horizontal) | Horizontal + vertical detection | Done |
| Validation before mask | Verhoeff only | Full validation (`is_valid_aadhaar_number`) | Done |
| Already-masked check | `check_image_text()` with pytesseract | `check_image_text()` with PaddleOCR | Done |

### QR Masking

| Field | Old | New | Status |
|-------|-----|-----|--------|
| Spatial check | None — all QR masked | `is_inside_aadhaar_by_area()` >= 50% overlap | Done |
| PAN QR | Incorrectly masked | Skipped (outside Aadhaar bbox) | Done |
| Already-masked QR | `is_qr_masked` label check | Same + spatial filter | Done |

### Orientation Detection

| Field | Old | New | Status |
|-------|-----|-----|--------|
| Angles tried | None (dead code) | 0, 45, 90, 135, 180, 225, 270, 315 | Done |
| Rotation method | `cv2.rotate()` only | Cardinal: `cv2.rotate()`, Diagonal: `cv2.warpAffine()` | Done |
| Scoring | N/A | `max(aadhaar_conf) + min(n, 3) * 0.05` | Done |
| Early exit | N/A | Conf >= 0.75 stops sweep | Done |
| Detection reuse | N/A | Winning angle's detections passed to pipeline | Done |

### Pipeline Integration

| Field | Old (Engine) | Old (Batch) | New (Both) | Status |
|-------|-------------|-------------|------------|--------|
| SKIP_KEYWORDS | Missing | Hardcoded locally | `core/config.SKIP_KEYWORDS` | Done |
| PAN check | Missing | Missing | `is_pan_card()` after OCR | Done |
| Spatial QR filter | Missing | Missing | Before `mask_yolo_detections()` | Done |
| GPU warmup | On startup | Missing | Both on startup | Done |
| Memory fraction | 0.7 (engine) | Missing | 0.7 configurable (both) | Done |
| Graceful shutdown | N/A (per-request) | Missing | `threading.Event()` + signals | Done |

---

## Features NOT Migrated (Pending Decision)

| Feature | Old Location | Description | Decision |
|---------|-------------|-------------|----------|
| `hw_number` | `batch.py` form path | PMAY handwritten number masking | See below |
| `uid_table` | `batch.py` form path | PMAY UID table region blanking | See below |
| `valid_image` filter | Both services | Skip non-Aadhaar documents | Intentionally removed — mask numbers everywhere |

---

## Security Fixes Applied

| Issue | Location | Fix |
|-------|----------|-----|
| Temp file PII exposure | `classifiers.py` | Removed — numpy array passed directly |
| No bounds clamping | `classifiers.py` | Added `max(0,x)`, `min(w,x)` on YOLO coords |
| `print()` leaking data | `masking.py` | Replaced with `log.debug()` |
| Plain bool for shutdown | `batch.py` | `threading.Event()` (thread-safe) |
| Hardcoded S3 bucket defaults | `batch.py` | Noted — env var required at runtime |

---

## Remaining Known Issues

| Issue | File | Severity | Notes |
|-------|------|----------|-------|
| `mkdtemp` without cleanup | `core/utils/file_utils.py:42` | Medium | PII in temp files |
| Full path in exceptions | `engine.py:208` | Low | Info disclosure |
| New OCR per detection | `masking.py:303` `check_image_text()` | Medium | Performance (creates instance each call) |
| S3 bucket hardcoded defaults | `batch.py:76-77` | Low | Should fail-loud if not set |
