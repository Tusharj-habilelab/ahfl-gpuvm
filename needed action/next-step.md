# Needed Action

1. First test on GPU server.
2. Then run full flow.

Notes:
- Keep #9 and #10 unchanged for now.
- Focus on break/hang behavior first.

What is #9?
- `orientation_hint_angle` field in file-level report is often None. This does not break processing, but means analytics/reporting may miss angle info.

What is #10?
- `lane_chosen` in file summary always picks the first page's lane. For mixed PDFs (some pages form, some card), this can misrepresent the file. No processing break, but reporting truth is reduced.

## Pending: failedPages + has_page_errors in DynamoDB (12-05-2026)

File: `services/batch-processor/batch.py` → `_update_to_completed()`

Problem:
- `totalPages=13`, `scannedPages=4`, but no top-level failed count.
- Status stays `COMPLETED` even when 9/13 pages errored.
- `has_page_errors` field missing — can't filter partial failures without scanning `pageReports`.

Change to apply (after GPU flow test passes):

1. Add after `scanned = ...` line:
```python
failed = total - scanned
has_page_errors = failed > 0
```

2. Add to UpdateExpression string:
```
"totalPages = :tp, scannedPages = :sp, maskedPages = :mp, failedPages = :fp, has_page_errors = :hpe, "
```

3. Add to ExpressionAttributeValues:
```python
":fp": failed,
":hpe": has_page_errors,
```

Result per record:
- `failedPages` = int count of pages with errors
- `has_page_errors` = true/false (filterable with DynamoDB FilterExpression)

Do NOT apply until GPU flow test is verified working.

---

## Applied: Silent-skip audit fixes (12-05-2026)

Trigger: `499_final.png` had `is_qr=3` but `is_qr_masked=0`, lane=uncertain, OCR aadhaar_confirmed=false, gate fb_confirmed=true. Old gates required OCR confirmation, so masking was silently skipped on a real Aadhaar card.

Three related silent-skip paths fixed in this pass:

1. **QR masking gate** (`core/pipeline.py` `_process_card_like_lane`, `pipeline-visualizer-per-step.py` card branch).
   - Added `gate_fb_confirmed = gate_result["fb_confirmed"]` as a third allow condition for `qr_masking_allowed`.
   - Spatial safety unchanged: QR still only masked inside Aadhaar bbox via `is_inside_aadhaar_by_area`.

2. **PAN / skip_keywords gate** (`core/pipeline.py` `_verify_skip_pan`).
   - Added `gate_fb_confirmed: bool = False` kwarg.
   - `confirmed = aadhaar_confirmed or gate_fb_confirmed` is now used to suppress `skip_keywords` and `pan_card` skips.
   - Reason: a real Aadhaar card whose OCR confirmation failed must not be skipped just because noisy OCR matched a PAN-ish pattern or a keyword.
   - Visualizer card branch updated to pass the same kwarg.

3. **Helper-label number fallback** (`core/ocr/masking.py` `mask_yolo_detections`).
   - Added `gate_fb_confirmed=False` kwarg, threaded from `core/pipeline.py` and visualizer.
   - When OCR verification fails on a helper `is_number` label, proportional fallback masking is now allowed if `gate_fb_confirmed=True` AND the box lies inside an Aadhaar bbox (`is_inside_aadhaar_by_area`).
   - Primary labels (`number`, `number_inverse`, `number_anticlockwise`) keep existing proportional-fallback behavior.
   - False-positive blast radius bounded by spatial-inside-Aadhaar check.

Verification:
- `get_errors` clean on all three files.
- Re-run failing job `image-test_input--20260512_080405` after next deploy and confirm:
  - `is_qr_masked == is_qr` for pages with `fb_confirmed=true`.
  - No PAN/skip_keyword false skip on real Aadhaar cards with noisy OCR.
  - Helper-label `is_number` detections inside Aadhaar bbox now produce a proportional mask, logged as `proportional-fallback (helper-label gate-confirmed)`.

Out of scope this pass:
- Lane label cosmetics (router threshold). `uncertain` lane still runs full card pipeline; behavior unchanged.
- CERSAI OCR-pattern skip in `find_aadhaar_patterns()` — affects pattern-based masking only, not YOLO masking.

---
## Static warnings status (06-05-2026)

Blocker now?
- No. These are not current runtime blockers.

Warnings tracked:
1. `services/api-gateway/main.py:169` — Path traversal warning. Current guards exist. Optional hardening pending.
2. `core/pipeline.py:45` — Global singleton warning. Current lock-protected OCR singleton is intentional.
3. `core/ocr/masking.py:720` — High cyclomatic complexity. Refactor pending.
4. `core/utils/angle_detector.py:92` — Large function warning. Refactor pending.

Action timing:
- Do not block GPU flow test for these.
- Revisit in cleanup/refactor pass after runtime verification.
