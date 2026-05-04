# Pipeline Flow Diagrams

## 1. CURRENT Pipeline (What Exists Now)

Both engine.py and batch.py run this same logic (duplicated):

```
IMAGE IN
  |
  v
+-------------------+     +-------------------+
| YOLO Main (main.pt)|     | YOLO Best (best.pt)|
| Detects: Aadhaar,  |     | Detects: Number,   |
| Number, QR, XX,    |     | QR, Masked variants|
| Masked variants    |     |                    |
+-------------------+     +-------------------+
  |                           |
  v                           v
+------------------------------------------+
| MERGE (IoU > 0.5 = duplicate)            |
| Keep higher confidence detection         |
| Output: merged_detections list           |
+------------------------------------------+
  |
  v
+------------------------------------------+
| CLASSIFIER (front_back_detect.pt)        |
| For each "Aadhaar" detection:            |
|   - Crop image region                    |
|   - Write to /tmp as JPEG  <-- SLOW      |
|   - Run classifier model                 |
|   - If class 0/1/2 (Front/Back/PVC)     |
|     -> KEEP detection                    |
|   - Else -> DROP detection               |
| Non-Aadhaar labels: always KEEP          |
+------------------------------------------+
  |
  v
+------------------------------------------+
| YOLO MASKING (mask_yolo_detections)      |
|                                          |
| For each detection:                      |
|   QR (any):                              |
|     -> Mask FULL box (black rectangle)   |  <-- PROBLEM: masks ALL QR
|                                          |      including PAN card QR
|   Number:                                |
|     -> Check if already masked (OCR 'x') |
|     -> If not: mask 68% of width/height  |  <-- PROBLEM: percentage-based
|                                          |      not digit-based
|   XX/Masked: skip                        |
+------------------------------------------+
  |
  v
+------------------------------------------+
| PaddleOCR                                |
|   - Resize image (max 1600px side)       |
|   - Run OCR on resized image             |
|   - Scale coordinates back to original   |
|   - Extract texts, boxes, confidences    |
+------------------------------------------+
  |
  v
+------------------------------------------+
| OCR MASKING (find_aadhaar_patterns +     |
|              mask_ocr_detections)         |
|                                          |
| Scans OCR tokens for:                    |
|   - "aadhaar"/"aadhar" keyword           |
|   - "cersai" keyword -> SKIP page        |
|   - 12-digit numbers (Verhoeff valid)    |
|   - 4-4-4 split numbers                  |
|   - "applicant aadhar" form patterns     |
|                                          |
| Masking:                                 |
|   number: mask 66% width                 |  <-- PROBLEM: percentage-based
|   number_split: mask full first 2 groups |
|   app_form_var1/2: mask offset region    |
+------------------------------------------+
  |
  v
SAVE IMAGE + RETURN REPORT
```

### Problems with Current Flow:
1. No orientation detection (rotated images fail)
2. QR masked unconditionally (PAN card QR gets masked)
3. 66-68% width masking (not 8-of-12 digits)
4. No first-digit validation (0/1 are invalid Aadhaar starts)
5. Classifier writes temp files to disk (slow)
6. No PAN card detection

---

## 2. NEW Pipeline (After All Phases)

```
IMAGE IN
  |
  v
========================================
  STEP 0: ORIENTATION SWEEP (Phase 2)
========================================
  |
  v
+------------------------------------------+
| find_best_orientation(image, yolo_main)  |
|                                          |
| For angle in [0, 45, 90, 135, 180,      |
|               225, 270, 315]:            |
|                                          |
|   1. Rotate image:                       |
|      Cardinal (0,90,180,270):            |
|        cv2.rotate() -- fast              |
|      Diagonal (45,135,225,315):          |
|        cv2.warpAffine() + white padding  |
|                                          |
|   2. Run YOLO main on rotated image      |
|                                          |
|   3. Score this angle:                   |
|      Has "Aadhaar" labels?               |
|        score = max(aadhaar_conf)         |
|                + min(n_aadhaar, 3)*0.05  |
|      No "Aadhaar" labels?               |
|        score = n_total_dets * 0.01       |
|                                          |
|   4. Early exit if aadhaar_conf >= 0.75  |
|                                          |
| OUTPUT:                                  |
|   - best_image (rotated to best angle)   |
|   - main_detections (REUSED later)       |  <-- KEY: no second YOLO main run
|   - best_angle (for logging)             |
+------------------------------------------+
  |
  v
========================================
  STEP 1: YOLO BEST + MERGE
========================================
  |
  v
+------------------------------------------+
| Run YOLO Best on best_image              |
|   (only 1 model run -- main was reused)  |
|                                          |
| Merge:                                   |
|   main_detections (from orientation)     |
|   + best_detections (just computed)      |
|   -> IoU > 0.5 = duplicate              |
|   -> Keep higher confidence              |
|                                          |
| OUTPUT: merged_detections                |
+------------------------------------------+
  |
  v
========================================
  STEP 2: AADHAAR GATE (Pre-Masking)
========================================

This is the decision layer. Three checks happen here:

+------------------------------------------+
|                                          |
| A. CLASSIFIER (front_back_detect.pt)     |
|    For "Aadhaar" detections:             |
|      Pass numpy crop directly (no disk)  |
|      If class 0/1/2 -> KEEP             |
|      Else -> DROP                        |
|                                          |
| B. PAN CHECK (Phase 3)                   |
|    For each confirmed "Aadhaar" crop:    |
|      Run PaddleOCR on crop               |
|      If text has "PAN" or matches        |
|        [A-Z]{5}[0-9]{4}[A-Z]            |
|      -> Mark as PAN false-positive       |
|      -> REMOVE from Aadhaar list         |
|                                          |
| C. SPATIAL QR CHECK (Phase 3)            |
|    Find all Aadhaar card bounding boxes  |
|    For each QR detection:                |
|      Calculate area overlap with each    |
|      Aadhaar bbox                        |
|      If overlap >= 50% of QR area:       |
|        -> KEEP QR for masking            |
|      Else:                               |
|        -> DROP QR (not inside Aadhaar)   |
|                                          |
| OUTPUT:                                  |
|   - aadhaar_card_boxes (for spatial)     |
|   - numbers_to_mask (all Number dets)    |
|   - qrs_to_mask (only inside-Aadhaar)   |
|   - pan_false_positives (logged)         |
+------------------------------------------+
  |
  v
========================================
  STEP 3: YOLO-BASED MASKING
========================================
  |
  v
+------------------------------------------+
| mask_yolo_detections()                   |
|                                          |
| QR codes:                                |
|   Only mask if in qrs_to_mask list       |  <-- FIXED: spatial guard
|   Mask full box                          |
|                                          |
| Numbers:                                 |
|   Check if already masked (OCR 'x')      |
|   Validate: is_valid_aadhaar_number()    |  <-- NEW
|     - 12 digits                          |
|     - First digit 2-9                    |
|     - No digit repeats > 4              |
|     - Verhoeff checksum                  |
|   Mask first 8 of 12 digits:            |  <-- FIXED: digit-based
|     8/12 = 0.667 of width (horizontal)  |
|     or height (vertical)                 |
+------------------------------------------+
  |
  v
========================================
  STEP 4: PaddleOCR
========================================
  |
  v
+------------------------------------------+
| Same as current:                         |
|   - Resize (max 1600px)                 |
|   - Run OCR                             |
|   - Scale coordinates back              |
|   - Extract texts, boxes, confidences   |
+------------------------------------------+
  |
  v
========================================
  STEP 5: OCR-BASED MASKING
========================================
  |
  v
+------------------------------------------+
| find_aadhaar_patterns() -- enhanced:     |
|   - Uses is_valid_aadhaar_number()       |  <-- NEW: first-digit check
|     instead of raw verhoeff_validate()   |
|   - Existing keyword matching stays      |
|   - Existing form patterns stay          |
|                                          |
| mask_ocr_detections() -- enhanced:       |
|   number: mask first 8/12 digits         |  <-- FIXED: digit-based
|   number_split: mask first 2 groups      |  <-- FIXED: 8 of 12
|   app_form_var1/2: same as current       |
+------------------------------------------+
  |
  v
SAVE IMAGE + RETURN REPORT
```

---

## 3. Pre-Masking Phase Detail (Orientation + Aadhaar Gate + Spatial)

These three form the "pre-masking intelligence layer":

```
                    IMAGE
                      |
                      v
        +---------------------------+
        | ORIENTATION SWEEP         |
        | Try 8 angles              |
        | YOLO main on each         |
        | Pick best by score        |
        | Early exit if conf >= 0.75|
        +---------------------------+
                      |
                      | Returns: best_image + main_detections
                      v
        +---------------------------+
        | YOLO BEST                 |
        | Run on best_image only    |
        +---------------------------+
                      |
                      | Returns: best_detections
                      v
        +---------------------------+
        | MERGE                     |
        | main_dets + best_dets     |
        | IoU dedup (threshold 0.5) |
        +---------------------------+
                      |
                      | Returns: merged_detections
                      v
    +--------------------------------------------+
    |            AADHAAR GATE                     |
    |                                            |
    |  merged_detections                         |
    |       |                                    |
    |       +---> "Aadhaar" labels               |
    |       |         |                          |
    |       |         v                          |
    |       |    CLASSIFIER                      |
    |       |    (front_back_detect.pt)           |
    |       |    Pass numpy crop directly         |
    |       |         |                          |
    |       |         v                          |
    |       |    Confirmed? ----NO----> DROP     |
    |       |         |                          |
    |       |        YES                         |
    |       |         |                          |
    |       |         v                          |
    |       |    PAN CHECK                       |
    |       |    (OCR on crop)                   |
    |       |    Has "PAN" text? ---YES--> DROP  |
    |       |         |                 (log it) |
    |       |         NO                         |
    |       |         |                          |
    |       |         v                          |
    |       |    aadhaar_card_boxes[]             |
    |       |                                    |
    |       +---> "QR" labels                    |
    |       |         |                          |
    |       |         v                          |
    |       |    SPATIAL CHECK                   |
    |       |    QR area overlap with            |
    |       |    aadhaar_card_boxes              |
    |       |         |                          |
    |       |    >= 50%? ---NO----> DROP QR      |
    |       |         |                          |
    |       |        YES                         |
    |       |         |                          |
    |       |         v                          |
    |       |    qrs_to_mask[]                   |
    |       |                                    |
    |       +---> "Number" labels                |
    |                 |                          |
    |                 v                          |
    |            numbers_to_mask[]               |
    |            (ALL numbers kept --             |
    |             validation at mask time)        |
    +--------------------------------------------+
                      |
                      v
              TO MASKING STEPS
              (YOLO mask + OCR mask)
```

---

## 4. Scoring Formula Explained

```
WHY DO WE NEED A SCORE?

When trying 8 angles, multiple angles might detect something.
We need to pick THE BEST angle.

Example scenario:
  Angle 0:   Detects 2 "Number" boxes (no "Aadhaar" label)
  Angle 90:  Detects 1 "Aadhaar" box at 0.82 confidence
  Angle 180: Detects 1 "Aadhaar" box at 0.45 confidence

SCORING:

  Angle 0:
    No Aadhaar detected -> fallback formula
    score = n_total_dets * 0.01 = 2 * 0.01 = 0.02

  Angle 90:
    Has Aadhaar -> main formula
    score = max(aadhaar_conf) + min(n_aadhaar, 3) * 0.05
    score = 0.82 + min(1, 3) * 0.05
    score = 0.82 + 0.05 = 0.87

  Angle 180:
    Has Aadhaar -> main formula
    score = 0.45 + min(1, 3) * 0.05 = 0.50

  WINNER: Angle 90 (score 0.87)

WHY THIS FORMULA:
  - max(aadhaar_conf): Higher confidence = better orientation
  - min(n_aadhaar, 3) * 0.05: Bonus for multiple cards (capped at 3)
    (Some pages have 2-3 Aadhaar cards -- more detected = better angle)
  - Fallback: If no Aadhaar at all, any detections slightly positive
    (better than nothing, but always loses to an angle with Aadhaar)

DO WE NEED IT?
  YES. Without scoring:
  - We'd pick first angle where conf >= 0.75 (early exit)
  - But if NO angle reaches 0.75, we need to compare
  - Score picks the best imperfect angle
  - Alternative: just use max(aadhaar_conf) alone
    -> Fails when 2 angles have same conf but different card counts
```

---

## 5. is_valid_aadhaar_number() Detail

```
CURRENT: verhoeff_validate(number)
  1. Remove hyphens and spaces
  2. Check: exactly 12 digits
  3. Check: no single digit appears > 4 times
  4. Run Verhoeff checksum algorithm
  -> Returns True/False

NEW: is_valid_aadhaar_number(number)
  1. Remove hyphens and spaces
  2. Check: exactly 12 digits
  3. Check: first digit is 2-9              <-- NEW
     (UIDAI rule: Aadhaar never starts
      with 0 or 1)
  4. Check: no single digit appears > 4 times
  5. Run Verhoeff checksum algorithm
  -> Returns True/False

WHY ADD FIRST-DIGIT CHECK:
  - Reduces false positives
  - Bank account numbers often start with 0 or 1
  - UIDAI officially reserves 2-9 as first digit
  - Example: 012345678901 -> passes Verhoeff but INVALID Aadhaar
```

---

## 6. Asyncio Explained (Batch Processor)

```
WHAT IS ASYNCIO DOING HERE?

The batch processor runs 3 model inferences per image:
  1. YOLO Main   (detect Aadhaar/Number/QR)
  2. YOLO Best   (detect Number/QR variants)
  3. PaddleOCR   (extract text)

CURRENT (BROKEN) PATTERN:

  For each image:
    loop1 = asyncio.new_event_loop()    <-- Create loop
    result1 = loop1.run_until_complete(  <-- Block until done
      run_in_threadpool(yolo_main)
    )
    loop1.close()                        <-- Destroy loop

    loop2 = asyncio.new_event_loop()    <-- Create ANOTHER loop
    result2 = loop2.run_until_complete(
      run_in_threadpool(yolo_best)
    )
    loop2.close()

    loop3 = asyncio.new_event_loop()    <-- Create ANOTHER loop
    result3 = loop3.run_until_complete(
      run_in_threadpool(ocr)
    )
    loop3.close()

  PROBLEMS:
  - Creates 3 event loops per image (expensive)
  - Each blocks sequentially (no actual parallelism!)
  - On ARM64 Mac: hangs because GIL + no CUDA
  - Overhead of loop creation > benefit

WHY IT EXISTS:
  Original idea: run YOLO main + YOLO best in PARALLEL
  On GPU with CUDA: models release GIL during GPU compute
  So 2 threads CAN overlap GPU work

AFTER ORIENTATION CHANGE:
  With detection reuse, the flow becomes:

  Step 0: Orientation runs YOLO main (multiple angles)
          -> REUSE winning main detections
  Step 1: Run YOLO best (1 inference)
  Step 2: PaddleOCR (1 inference)

  YOLO main is no longer a separate step!
  Only YOLO best + OCR remain.

OPTIONS:

  A. SYNCHRONOUS (simple):
     yolo_best_result = yolo_best(image)
     ocr_result = ocr.ocr(image)
     -> ~20ms slower per image (sequential)
     -> Works on ALL platforms (GPU, CPU, ARM64)

  B. PARALLEL (faster on GPU):
     Use single shared ThreadPoolExecutor
     Run yolo_best AND ocr in parallel
     -> ~10ms faster per image on GPU
     -> May hang on ARM64 CPU-only

  C. AUTO-DETECT (flexible):
     if torch.cuda.is_available():
         parallel mode (ThreadPoolExecutor)
     else:
         synchronous mode
     -> Best of both worlds
     -> More code paths to test

FOR ARM64 CPU LINUX:
  - Option A (synchronous) is safest
  - Option C gives you GPU speed when available
  - Option B would hang on ARM64 CPU
```

---

## 7. ARM64 Linux Compatibility

```
PLATFORM: ARM64 (aarch64) Linux, CPU-only

PyTorch:      YES - official aarch64 wheels available
PaddleOCR:    PARTIAL - CPU wheels exist, GPU wheels x86-only
Ultralytics:  YES - pure Python, works if PyTorch works
OpenCV:       YES - aarch64 wheels available

KEY CONCERN:
  PaddlePaddle on ARM64 is CPU-only.
  No CUDA acceleration possible on ARM.
  Inference will be slower (~3-5x vs GPU).

  asyncio parallel mode will NOT help on ARM64
  (no CUDA = GIL blocks threads = no real parallelism)

RECOMMENDATION:
  -> Use synchronous mode on ARM64
  -> Auto-detect: if no CUDA, force synchronous
```
