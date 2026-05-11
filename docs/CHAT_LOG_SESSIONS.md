# AHFL Masking — Full Chat Session Log

> Covers all compacted sessions from 2026-04-30.
> Raw turn-by-turn transcripts are at:
> `~/.claude/projects/-Users-tusharjain-projects-ahfl-working-Gpu/*.jsonl`

---

## Session 1 — OCR Masking + Orientation Models

### What was built

#### Change 1–5: OCR Masking Types (core/ocr/masking.py)

5 missing masking types ported from `bulk.py` into `core/ocr/masking.py`:

| Type | Trigger |
|------|---------|
| `aadhaar_card_applicant` | fuzzy "aadhaar card" + next_next = "applicant" |
| `aadhaarcard_applicant` | alternate spelling variant |
| `aadhaar_uid` | "aadhaar" + "uid"/"vid" in next word, no 4-digit number, not "uidai" |
| `aadhar_number_pmy_hw` | "aadhar" + "uid" + `hw_found=True`, skip if preceded by "applicant" |
| `aadhar_table_pmy_hw` | "applicant" fuzzy + "aadhar" + "uid" + `hw_found=True` + "with" precedes |

Added `uid_table_masking_coordinates(x1, x2, y1, y2, tokens_list)` helper:
- Scans OCR tokens for spatial overlap >50% by area with given bounding box
- Returns max y2 of overlapping rows (dynamic bottom-edge detection for UID tables)

Added 2 masking branches to `mask_ocr_detections`:
- `aadhaar_uid`: dynamic height via `uid_table_masking_coordinates`
- `aadhar_table_pmy_hw`: `x1_mask = x1`, `x2_mask = x1 + 2.5*w`, dynamic y2 via helper

#### Change 6: doc_orientation model (core/ocr/paddle.py)

```python
from paddleocr import PaddleOCR, DocImgOrientationClassification

_doc_ori_model = None

def get_doc_orientation_model() -> DocImgOrientationClassification:
    global _doc_ori_model
    if _doc_ori_model is None:
        _doc_ori_model = DocImgOrientationClassification()
    return _doc_ori_model
```

Model: `PP-LCNet_x1_0_doc_ori` — 4 classes (0°/90°/180°/270°), 99.06% accuracy, 7MB, ~3ms CPU.

#### Change 7: Orientation hint in YOLO sweep (core/utils/angle_detector.py)

```python
def _get_doc_orientation_hint(image: np.ndarray) -> int:
    try:
        model = get_doc_orientation_model()
        result = model.predict(image)[0]
        label = result.json["res"]["label_names"][0]
        return int(label)
    except Exception as e:
        log.debug(f"doc_orientation hint failed: {e}")
        return 0
```

Pre-check wired in `find_best_orientation` — if 0° score < threshold, tries doc_ori hint angle first. Falls back to full sweep if hint fails. No regression.

#### Change 8: Hard orientation correction for forms (core/pipeline.py)

```python
def _correct_doc_orientation(image: np.ndarray) -> np.ndarray:
    try:
        model = get_doc_orientation_model()
        result = model.predict(image)[0]
        angle = int(result.json["res"]["label_names"][0])
        if angle == 90:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if angle == 180:
            return cv2.rotate(image, cv2.ROTATE_180)
        if angle == 270:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    except Exception as e:
        log.debug(f"doc_orientation correction failed: {e}")
    return image
```

Form path (else branch) calls `_correct_doc_orientation(image)` before OCR. Hard correction — YOLO produces no card bbox for forms so there was no fallback previously. Sideways forms were returning empty OCR.

### Why cls cannot be used for orientation

- `cls` (`use_angle_cls=True`) = PaddleOCR text-line orientation, 2 classes (0°/180°), runs on DBNet crops
- DBNet (text detection) requires an upright image to find text boxes
- Pipeline order: doc_ori → DBNet → cls per box → CRNN
- cls is downstream of the orientation problem — it cannot help decide orientation

### Decisions made

- Lazy singleton in `paddle.py` — both `angle_detector.py` and `pipeline.py` share one model instance
- doc_ori used as hint (not hard correction) for card path — YOLO sweep is ground truth (conf >= 0.75)
- doc_ori used as hard correction for form path — no alternative exists

---

## Session 2 — Production Readiness Review

### Constraint: fully offline / air-gapped GPU VM

Client processes all documents locally. No internet access on the GPU VM. All models must be pre-bundled.

### Multi-angle production review findings

#### Offline / Air-gap (critical)

| Item | Status |
|------|--------|
| `PP-LCNet_x1_0_doc_ori` auto-downloads on first call | Must pre-bundle in Docker image |
| PaddleOCR model weights auto-download | Must pre-bundle |
| YOLO weights | Must be at paths set in `config.py` |
| No outbound calls in pipeline code | Safe once models bundled |

#### DynamoDB (not MySQL)

- `services/batch-processor/batch.py` uses DynamoDB for job tracking
- Job records keyed by `job_id`, status: `pending` / `processing` / `done` / `failed`
- No MySQL anywhere in the codebase

#### Logging

- `core/pipeline.py`, `core/ocr/masking.py`, `core/utils/angle_detector.py` — structured logging throughout
- Every masking type detection logs at DEBUG
- Orientation decisions log at DEBUG with angle + confidence
- DynamoDB writes log at INFO
- Enable full logging: `LOG_LEVEL=DEBUG`

### Pending items

| Item | Status |
|------|--------|
| Live inference test on PMAY forms | Not done — need test images |
| `use_angle_cls` → `use_textline_orientation` (paddle.py:30) | Pending (PaddleOCR v3.x deprecation) |
| batch.py skip keywords vs bulk.py parity check | Pending |
| Pre-bundle doc_ori model weights in Dockerfile | Pending |

---

## Files changed across all sessions

| File | What changed |
|------|-------------|
| `core/ocr/masking.py` | uid_table_masking_coordinates + 5 detection blocks + 2 masking branches |
| `core/ocr/paddle.py` | DocImgOrientationClassification import + get_doc_orientation_model() singleton |
| `core/utils/angle_detector.py` | _get_doc_orientation_hint + pre-check in find_best_orientation |
| `core/pipeline.py` | _correct_doc_orientation + form path call + import |
| `core/config.py` | Config updates |
| `core/__init__.py` | Init updates |
| `services/masking-engine/engine.py` | Engine updates |
| `services/batch-processor/batch.py` | Batch processor updates |
| `core/utils/__init__.py` | Utils init |
| `core/spatial.py` | Spatial helpers |
| `core/classifiers.py` | Classifier updates |
| `core/ocr/__init__.py` | OCR init |
| `core/aadhaar_gate.py` | Gate logic |
| `docs/PIPELINE_FLOW.md` | Pipeline flow diagram |
| `docs/PIPELINE_CHANGES.md` | Change documentation |
| `docs/CHANGE_LOG_OCR_ORIENTATION.md` | Full orientation model change log |
| `docs/PENDING_DECISION_greyscale_preprocessing.md` | Open decision on greyscale preprocessing |

---

## Raw transcript locations

```
~/.claude/projects/-Users-tusharjain-projects-ahfl-working-Gpu/baedaee0-3270-4ab7-b873-d7f5e6933115.jsonl
```

Additional sessions in same folder — sorted by timestamp.
