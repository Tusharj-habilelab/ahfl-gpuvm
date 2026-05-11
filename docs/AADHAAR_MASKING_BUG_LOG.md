# Aadhaar Masking Bug Log

Date: 11-05-2026

## Scope
This file tracks Bug 1 and Bug 2 findings, root causes, code changes, and behavior impact for AHFL masking.

---

## Bug 1: Handwritten Aadhaar in forms not masked

### Symptom
- Line-11 style form rows (Applicant / Co-Applicant Aadhaar) sometimes remained unmasked.
- OCR produced noisy text such as merged tokens, split tokens, or alpha-digit confusion.

### Root cause
- Existing OCR pattern checks relied on clean `\d{12}` or clean `4-4-4` token splits.
- Handwritten OCR noise caused checks to fail before validation.

### Decision
- Keep fix OCR-only for forms.
- Do not add YOLO dependency for this bug path.

### Implemented change
- Added OCR digit-noise normalization helper in `core/ocr/masking.py`:
  - `_normalize_ocr_digits()`
  - `_merge_token_coordinates()`
  - `_coords_bbox_key()`
- Added form-lane-only recovery branch in `find_aadhaar_patterns(tokens_list, form_lane_only=False)`:
  - scans 1/2/3-token spans
  - normalizes OCR noise (e.g. O→0, I/l→1, S→5, B→8)
  - requires 12 digits + `is_valid_aadhaar_number()` (Verhoeff path unchanged)
  - appends `type="number_form_hw_noise"`
  - suppresses duplicate bbox regions

### Lane scope
- **Applied only to form lane** via `pipeline.py`:
  - `_process_form_lane`: `find_aadhaar_patterns(..., form_lane_only=True)`
  - `_process_card_like_lane`: `find_aadhaar_patterns(..., form_lane_only=False)`

### Impact
- Improves masking for noisy handwritten Aadhaar patterns in form documents.
- Card lane OCR behavior remains unchanged.

---

## Bug 2: First digit leak in OCR number masking bbox

### Symptom
- In some table UID masks, first digit remained visible due to bbox left-edge drift.

### Root cause
- OCR token bbox could start slightly right of true first digit.
- Fixed-ratio masking from token x1 could under-cover left edge.

### Status
- Accepted direction: bbox correction approach is valid.
- Current implementation context already includes left-padding in number masking paths.
- Further adaptive tuning can be added if new artifacts still show left-edge leaks.

---

## Why these choices
- Privacy-safe direction: recover noisy valid Aadhaar using checksum validation.
- Controlled blast radius: form-lane flag isolates Bug 1 behavior.
- Debug traceability: each path logs recovery decisions.

---

## Files changed for this bug cycle
- `core/ocr/masking.py`
- `core/pipeline.py`
- `docs/AADHAAR_MASKING_BUG_LOG.md`
