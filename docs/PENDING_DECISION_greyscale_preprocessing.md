# PENDING DECISION: Greyscale + Dilation Preprocessing

**Date:** 2026-04-29
**Status:** WAITING — confirm with colleague before proceeding

---

## Question

Should main.pt receive greyscale + dilated input, or RGB like the model spec says?

## What the model spec says

File: `docs/model-specification.md` (line 262)

```
Input Channels    : 3 — RGB (all models)
```

All 3 models (main.pt, best.pt, front_back_detect.pt) have first layer `Input Channels: 3`.
No mention of greyscale or dilation anywhere in the spec.

## What was discussed in the plan

The plan (`enchanted-growing-bumblebee.md`) says:

- main.pt needs greyscale + dilation before inference (matches training data)
- best.pt is trained on RGB — no greyscale needed
- front_back_detect.pt uses greyscale (reuse same grey object)

Preprocessing proposed:
```python
grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
kernel = np.ones((2, 2), np.uint8)
dilated = cv2.dilate(grey, kernel, iterations=1)
```

## Current code state

`core/aadhaar_gate.py` currently has:
- `_preprocess_greyscale()` function that creates grey + dilated
- main.pt receives `dilated` (1-channel, auto-expanded to 3 by Ultralytics)
- front_back_detect.pt receives `grey` (1-channel)
- best.pt receives RGB crop (correct either way)

## What needs to happen

1. Confirm with colleague: Was main.pt trained on dilated greyscale images or RGB?
2. If RGB: revert `_preprocess_greyscale()`, pass BGR directly to all models
3. If greyscale+dilated: keep current code, update model-specification.md to document this

## Impact if wrong

- If we feed RGB to a model trained on greyscale: lower detection accuracy
- If we feed greyscale to a model trained on RGB: lower detection accuracy
- Ultralytics YOLO handles 1-channel input by stacking to 3-channel (grey, grey, grey) — it won't crash either way

## Also discussed: already-masked detection improvement

User proposed: if OCR reads only 4 digits (out of 12), treat as already masked.
Logic:
```python
digits_found = sum(1 for c in text if c.isdigit())
if digits_found <= 4 and digits_found > 0:
    return True  # only last 4 visible = already masked
```
This handles white-masked, handwritten-masked cases that current x/y/k check misses.
Status: NOT YET IMPLEMENTED — implement after greyscale decision is resolved.
