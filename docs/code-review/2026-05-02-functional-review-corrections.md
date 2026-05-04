# Code Review: Functional Corrections
**Date**: 2026-05-02
**Scope**: `core/pipeline.py`

## Fixed now

1. Skip-keyword false skip on confirmed card flow
- Problem: skip-keyword check ran even when Aadhaar card confirmation was true.
- Fix: skip-keyword check now bypasses confirmed Aadhaar card text.

2. Dropped orientation-corrected image in card fallback OCR path
- Problem: `_run_ocr_for_card_path()` corrected image locally but did not return it.
- Impact: downstream masking could run on pre-corrected frame in fallback branch.
- Fix: function now returns updated image; caller now uses returned image.

## Remaining functional checks (not patched in this pass)

1. `orientation_hint_angle` field is always `None` in reports.
- If this field is required by downstream analytics, populate it from angle detector output.

2. File-level `lane_chosen` in batch DB summary picks first seen page lane.
- For mixed-lane PDFs, this can hide page-level diversity.
- Keep page-level truth in `pageReports`; optionally store `lane_counts` at file level.
