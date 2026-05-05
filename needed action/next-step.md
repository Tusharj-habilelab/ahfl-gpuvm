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
