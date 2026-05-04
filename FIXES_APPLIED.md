# Fixes Applied — 2026-05-01

Resolved 5 code issues from known_issues.md. Summary of changes per file.

---

## Issue #20 — No env var validation at startup

**Files:** `core/config.py`, `services/batch-processor/batch.py`, `services/masking-engine/engine.py`

**What changed:**
- Added `validate_required_env_vars()` function in config.py
- Validates: TABLE_NAME, AWS_REGION, RAW_BUCKET, MASKED_BUCKET
- Called at startup in batch.py and engine.py

**Why:** Missing env vars crashed mid-run with cryptic errors. Now fails at startup with clear message.

**How to verify:**
```bash
# Run without RAW_BUCKET env var
python batch.py --s3

# Should fail immediately with:
# RuntimeError: Missing required environment variables: RAW_BUCKET, ...
```

---

## Issue #10 — File size check in engine.py (masking-engine)

**Files:** `services/masking-engine/engine.py`, `core/config.py`

**What changed:**
- MAX_FILE_SIZE now reads from `core.config` (was hardcoded 10 MB)
- File size check moved BEFORE saving file to disk
- Uses Content-Length header (no wasted disk I/O)
- Returns HTTP 413 (not 422) when file exceeds limit

**Why:** 
1. Hardcoded 10 MB couldn't be changed per environment
2. Old code saved file then checked — wasted disk I/O on large uploads
3. HTTP 413 is correct status for payload too large (RFC 7231)

**How to verify:**
```bash
# Upload file > 10 MB to /mask endpoint
curl -F "file=@large.pdf" http://localhost:8001/mask

# Should fail with HTTP 413 before saving
```

---

## Issue #11 — PDF chunking in engine.py

**Files:** `services/masking-engine/engine.py`

**What changed:**
- `_mask_pdf()` now processes PDFs in 10-page chunks
- Was loading all pages at once with `convert_from_path()`
- Now uses `first_page` and `last_page` parameters

**Why:** A 50-page PDF at 200dpi used 1–2 GB RAM all at once. Chunking keeps peak RAM constant (~200 MB per chunk). Matches batch.py logic.

**How to verify:**
```bash
# Monitor RAM while processing 100-page PDF via /mask endpoint
# Peak memory should stay < 500 MB (not spike to 2+ GB)
```

---

## PaddleOCR silent failures — Logging added

**File:** `core/ocr/ocr_adapter.py`

**What changed:**
- Added `import logging` and `log = logging.getLogger(__name__)`
- Exception handlers now log warnings instead of silently returning None
- Three locations: `_normalize_bbox()`, `_append_v3_result()`, `adapt_paddle_result()`

**Why:** OCR failures were invisible in logs. Debugging was impossible. Now all failures logged at WARNING level.

**How to verify:**
```bash
# Run masking on a corrupted/malformed PDF
# Should see log entries like:
# WARNING - core.ocr.ocr_adapter - Failed to normalize bbox ...: ...
```

---

## classifiers.py — Missing logging import

**File:** `core/classifiers.py`

**What changed:**
- Added `import logging`
- Added `log = logging.getLogger(__name__)`

**Why:** Consistent logging across all core modules. Module was used by aadhaar_gate.py which needed to log failures but classifiers.py had no logger.

**How to verify:**
```bash
# Check that classifier logs any warnings during detection:
# grep "classifiers" logs/
```

---

## Summary

| Issue | File(s) | Status |
|-------|---------|--------|
| #20 Env var validation | config.py, batch.py, engine.py | ✅ Fixed |
| #10 File size check | engine.py, config.py | ✅ Fixed |
| #11 PDF chunking | engine.py | ✅ Fixed |
| PaddleOCR logging | ocr_adapter.py | ✅ Fixed |
| Classifiers logging | classifiers.py | ✅ Fixed |

**GPU Server Sync:** All 5 files listed in GPU_SYNC_PENDING.md. Copy to GPU server before next batch run.

**Testing:** Run on GPU server with test PDF (10+ pages, >5 MB) to verify all fixes work together.
