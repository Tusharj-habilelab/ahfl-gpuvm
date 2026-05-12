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
