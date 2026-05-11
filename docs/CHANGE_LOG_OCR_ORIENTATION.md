# Change Log — OCR Masking Types + Orientation Models

## Session: 2026-04-29

---

## Change 1: `uid_table_masking_coordinates` helper

**File:** `core/ocr/masking.py`

**What:** Added `uid_table_masking_coordinates(x1, x2, y1, y2, tokens_list)` function.

**Why:** `aadhaar_uid` and `aadhar_table_pmy_hw` masking types need to extend their mask rectangle
downward to cover the entire UID table — not just a fixed pixel offset. This function scans all
OCR tokens, finds which ones spatially overlap the mask region (>50% overlap by area), and returns
the bottom edge of the lowest overlapping row. Ported directly from `bulk.py` lines 375–403.

---

## Change 2: 5 Missing Detection Blocks in `find_aadhaar_patterns`

**File:** `core/ocr/masking.py`

**What:** Added 5 new detection blocks inside the `for i in range(...)` loop.

**Why:** `find_aadhaar_patterns` only detected 4 types (`number`, `number_split`, `app_form_var1`,
`app_form_var2`). The original `bulk.py` had 9 types. The 5 missing types were causing PII to go
unmasked on PMAY forms and application forms. Masking code for 3 of these existed as dead code in
`mask_ocr_detections` — never triggered because no detection ever produced those types.

| Type | Trigger | Document |
|---|---|---|
| `aadhaarcard_applicant` | word fuzzy-matches "aadhaar card" + next_next matches "applicant" | PMAY Additional form |
| `aadhaar_card_applicant` | same trigger, word is fuzzy match only (not literal) | PMAY Additional form |
| `aadhaar_uid` | "aadhaar" followed by "uid"/"vid", no 4-digit number in next_next, not "uidai" | PMAY Additional form table |
| `aadhar_number_pmy_hw` | "aadhar" + "uid", `hw_found=True`, skips if preceded by "applicant" | PMAY Beneficiary Handwritten |
| `aadhar_table_pmy_hw` | "applicant" fuzzy + "aadhar" + "uid", `hw_found=True`, "with" precedes | PMAY Beneficiary Handwritten table |

`hw_found` flag (already tracked) is set when both `disb_dt_found` AND `loan_code_found` are True,
identifying PMAY handwritten beneficiary forms.

---

## Change 3: 2 Missing Masking Branches in `mask_ocr_detections`

**File:** `core/ocr/masking.py`

**What:** Added `aadhaar_uid` and `aadhar_table_pmy_hw` elif branches to `mask_ocr_detections`.

**Why:** These 2 types were completely absent from `mask_ocr_detections` — even if detection fired,
no rectangle would have been drawn. Both use `uid_table_masking_coordinates` to dynamically size
the mask height instead of a fixed offset. Guard condition `> 5px` prevents zero-height masks.

Geometry (ported from `bulk.py` lines 491–527):

| Type | x1_mask | x2_mask | y1_mask | y2_mask |
|---|---|---|---|---|
| `aadhaar_uid` | `x1 - 1.08w` | `x1_mask + 2.5w` | `y2 + 1.25h` | dynamic via `uid_table_masking_coordinates` |
| `aadhar_table_pmy_hw` | `x1` | `x1 + 2.5w` | `y2` | dynamic via `uid_table_masking_coordinates` |

---

## Change 4: `get_doc_orientation_model` in `paddle.py`

**File:** `core/ocr/paddle.py`

**What:** Added `DocImgOrientationClassification` import and `get_doc_orientation_model()` lazy
singleton function.

**Why:** Both `angle_detector.py` and `pipeline.py` need access to `PP-LCNet_x1_0_doc_ori`.
Centralising the loader in `paddle.py` ensures one instance is shared across all call sites
(7MB model, loaded once, cached permanently to `/root/.paddlex`).

---

## Change 5: `doc_orientation` Pre-Check in Orientation Sweep

**File:** `core/utils/angle_detector.py`

**What:** Added `_get_doc_orientation_hint(image)` helper and wired it into `find_best_orientation`
as a pre-check before the 8-angle YOLO sweep.

**Why:** The YOLO sweep worst case is 8 × 3 model calls = 24 inference passes. `PP-LCNet_x1_0_doc_ori`
predicts document rotation (0/90/180/270°) in ~3ms. If the hint angle is tried first and YOLO
confirms `max_aadhaar_conf >= 0.75`, the remaining sweep is skipped entirely.

Flow:
```
1. Score 0° (always runs)
2. If 0° did not pass threshold:
   a. Run doc_orientation → get hint angle
   b. If hint_angle != 0: rotate + run YOLO gate once
   c. If conf >= 0.75 → return immediately (skip remaining 7 angles)
   d. If conf < 0.75 → fall through to normal sweep (no regression)
3. Normal 8-angle sweep continues as before
```

**Why `cls` cannot do this:** `cls` runs per text-line crop inside PaddleOCR. Those crops only
exist after DBNet text detection, which runs inside `_run_ocr_on_region`, which runs after the
orientation sweep is already complete. `cls` is downstream of the problem it would need to solve.

---

## Change 6: `_correct_doc_orientation` in Form Path

**File:** `core/pipeline.py`

**What:** Added `_correct_doc_orientation(image)` helper. Called in the `else` branch of the
OCR section (form path — no Aadhaar card crops detected).

**Why:** The YOLO orientation sweep handles cards. For application forms and PMAY documents
(no card bbox), if the form is scanned at 90°/270°, DBNet text detection returns empty results —
`cls` never runs, OCR output is empty, PII is never masked. Silent failure.

`_correct_doc_orientation` rotates the image to upright before `_run_ocr_on_region`, ensuring
DBNet gets a correct image and finds text lines. Card path is NOT affected.

```
CARD PATH                          FORM PATH
─────────────────────────────      ──────────────────────────────
angle_detector.py sweep            pipeline.py else branch

doc_ori hint → try 1 angle         _correct_doc_orientation()
YOLO confirms → early exit            PP-LCNet → 0/90/180/270°
Falls back → 8-angle sweep            rotate image to upright
                                   _run_ocr_on_region()
                                   DBNet finds text lines
                                   cls fixes flipped lines
                                   CRNN reads text
                                   find_aadhaar_patterns()
                                   mask_ocr_detections()
```

---

## Files Modified

| File | Change |
|---|---|
| `core/ocr/masking.py` | uid_table_masking_coordinates + 5 detection blocks + 2 masking branches |
| `core/ocr/paddle.py` | DocImgOrientationClassification import + get_doc_orientation_model() |
| `core/utils/angle_detector.py` | _get_doc_orientation_hint + doc_ori pre-check in find_best_orientation |
| `core/pipeline.py` | get_doc_orientation_model import + _correct_doc_orientation + form path call |

## Files NOT Modified

| File | Reason |
|---|---|
| `services/masking-engine/engine.py` | Uses core functions only — no change needed |
| `services/batch-processor/batch.py` | Uses core functions only — no change needed |
| `core/aadhaar_gate.py` | Card gate logic unchanged |
| `core/config.py` | No new config flags needed |
