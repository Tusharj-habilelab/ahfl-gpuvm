# Code Review: Core Pipeline + Batch + Masking Engine
**Date**: 2026-05-02  
**Scope**: `core/pipeline.py`, `services/batch-processor/batch.py`, `services/masking-engine/engine.py`, `core/db/database.py`, `core/config.py`  
**Ready for Production**: No  
**Critical Issues**: 2

## Review Plan Used
- OWASP A01 Broken Access Control
- OWASP A04 Insecure Design / DoS controls
- OWASP A05 Security Misconfiguration
- OWASP A09 Logging/Monitoring + PII handling
- Zero Trust checks for internal service assumptions

## Priority 1 (Must Fix) ⛔

### 1) PII disclosure path in batch PDF fallback
**File**: `services/batch-processor/batch.py`  
**Location**: `_process_pdf()` error branch when blank-page write fails

**Issue**
- If masking fails and blank replacement also fails, code appends original page image path.
- This can produce output PDF containing unmasked PII.

**Impact**
- Direct data leak risk.
- Violates masking guarantee.

**Fix**
- Never include original page after masking failure.
- Fail the file hard (`ERROR`) or stop PDF generation.
- Optionally produce a deterministic redacted placeholder page from in-memory constant if disk write fails.

---

### 2) No auth guard on masking-engine endpoints
**File**: `services/masking-engine/engine.py`  
**Location**: `/mask`, `/output/{filename}`, `/health*`

**Issue**
- Endpoints are callable without token/key validation.
- Service assumes network isolation.

**Impact**
- Any exposed route allows unauthenticated file processing and output retrieval.
- Enables abuse and potential data exfiltration.

**Fix**
- Enforce service-to-service auth (HMAC/JWT/API key).
- Require auth for `/mask` and `/output/*` at minimum.
- Keep health endpoints either internal-only or auth-protected.

## Priority 2 (Should Fix) ⚠️

### 3) CORS wildcard on file-processing service
**File**: `services/masking-engine/engine.py`  
**Location**: `allow_origins=["*"]`

**Issue**
- Wildcard CORS allows browser-origin requests from any origin.

**Impact**
- Increases attack surface if endpoint is reachable.

**Fix**
- Move allowed origins to config and use explicit allowlist.

---

### 4) Missing max-page guard in masking-engine PDF path
**File**: `services/masking-engine/engine.py`  
**Location**: `_mask_pdf()`

**Issue**
- Batch path enforces `MAX_PDF_PAGES`; engine path does not.

**Impact**
- DoS risk via huge PDFs.

**Fix**
- Reuse `MAX_PDF_PAGES` from `core.config` in engine path.

---

### 5) Weak upload validation (extension-only)
**File**: `services/masking-engine/engine.py`  
**Location**: `mask_file()`

**Issue**
- Validation checks extension and size only.
- No content-type or magic-byte validation.

**Impact**
- Malformed/hostile inputs can hit parser stack.

**Fix**
- Validate MIME and file signature before processing.
- Reject mismatch between extension and signature.

## Priority 3 (Good Hardening) ✅

### 6) Internal detail leakage in error response
**File**: `services/masking-engine/engine.py`  
**Location**: `HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")`

**Issue**
- Raw exception details returned to caller.

**Fix**
- Return generic message to client.
- Log full detail server-side with request id.

---

### 7) Over-broad exception handling in DB layer
**File**: `core/db/database.py`

**Issue**
- `except Exception` masks root cause classes.

**Fix**
- Catch `ClientError` separately for actionable handling.

## Positive Findings
- Verification-before-masking order is now implemented in lane flow.
- Config centralization improved threshold governance.
- DynamoDB write path keeps backward compatibility while adding new tracking fields.
- S3 preflight checks exist in batch mode.

## Minimal Patch Sequence Recommended
1. Remove unmasked-page fallback in batch `_process_pdf()`.
2. Add auth dependency/middleware in masking engine.
3. Replace wildcard CORS with allowlist from config.
4. Add `MAX_PDF_PAGES` guard in engine `_mask_pdf()`.
5. Add MIME + signature validation for uploads.
6. Replace 500 raw detail with generic error contract.

## Verification Checklist
- Upload oversized and huge-page PDFs → rejected with clear status.
- Unauthorized request to `/mask` and `/output/*` → 401/403.
- Mask failure path never outputs unmasked source page.
- CORS only allows configured origins.
- Logs contain trace id; API response does not leak internals.