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
