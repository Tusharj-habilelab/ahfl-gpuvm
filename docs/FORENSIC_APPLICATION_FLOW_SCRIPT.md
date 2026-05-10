# AHFL Forensic Flow Script (Image to Final Mask)

This is an execution script you can read line-by-line and convert directly into a flow diagram.
It is based on current runtime code in:

- `services/masking-engine/engine.py`
- `core/pipeline.py`
- `core/router.py`
- `core/ocr/paddle.py`
- `core/ocr/masking.py`
- `core/classifiers.py`
- `core/aadhaar_gate.py`
- `core/utils/angle_detector.py`

---

## 0) Runtime Defaults (from config)

```text
ROUTER_ENABLED=true
ROUTER_CONFIDENCE_THRESHOLD=0.55
ROUTER_OCR_LITE_MAX_TOKENS=30
ROUTER_OCR_LITE_MAX_SIDE=800
PADDLE_OCR_MAX_SIDE=1600 (min floor 640)
ORIENTATION_ENABLED=true
ORIENTATION_ANGLES=[0,45,90,135,180,225,270,315]
SKIP_KEYWORDS={"statement","screening","sampling","bharatpe","phonepe","espay"}
```

---

## 1) Entry Script: `/mask` API Request

Pseudo-script from `services/masking-engine/engine.py`:

```python
def MASK_API_REQUEST(upload_file):
    correlation_id = uuid4()
    start_timer()

    ext = suffix(upload_file.name).lower()
    if ext not in {"pdf", "jpg", "jpeg", "png"}:
        raise HTTP 422

    content_length = get_upload_size(upload_file)
    if content_length > MAX_FILE_SIZE:
        raise HTTP 413

    output_path = save_uploaded_file_to_disk(upload_file)

    try:
        if ext == "pdf":
            page_reports = MASK_PDF(output_path)
        else:
            page_reports = {"1": MASK_SINGLE_IMAGE(output_path)}

        total_pages = len(page_reports)

        # Loop 1: aggregate masked-page count at endpoint level
        total_masked = 0
        for p in page_reports.values():
            if p.get("is_number_masked", 0) > 0 or p.get("is_qr_masked", 0) > 0:
                total_masked += 1

        return {
            "status": 200,
            "fileName": output_filename,
            "total_pages": total_pages,
            "total_pages_masked": total_masked,
            "page_reports": page_reports
        }
    except Exception:
        delete_output_file(output_path)
        raise HTTP 500
```

---

## 2) Single Image Wrapper Script

Pseudo-script from `engine.py::_mask_single_image`:

```python
def MASK_SINGLE_IMAGE(image_path):
    image = cv2.imread(image_path, IMREAD_COLOR)
    if image is None:
        raise ValueError("Cannot read image")

    if image.ndim == 2:
        image = cv2.cvtColor(image, GRAY2BGR)

    masked_image, report = process_image(image, skip_keywords_enabled=True)

    ok = cv2.imwrite(image_path, masked_image)
    if not ok:
        raise IOError("Failed to write masked image")

    return report
```

---

## 3) Core Main Script: `process_image(image)`

Pseudo-script from `core/pipeline.py`:

```python
def process_image(image, skip_keywords_enabled=True, debug=False):
    if image is None or image.size == 0:
        raise ValueError

    # Normalize channels
    if image.ndim == 2:
        image = cv2.cvtColor(image, GRAY2BGR)
    elif image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, BGRA2BGR)

    stats = {}
    ocr = _get_ocr()  # singleton, lock-protected

    # Router default
    router_result = {"lane": "uncertain", "confidence": 0.0, "reasoning": "router_disabled"}

    if ROUTER_ENABLED:
        ocr_tokens = run_ocr_lite_for_routing(image, ocr=ocr)
        router_result = classify_document_lane(
            ocr_tokens,
            confidence_threshold=ROUTER_CONFIDENCE_THRESHOLD,  # default 0.55
            debug=debug
        )
        stats["router_confidence"] = router_result["confidence"]

    lane = router_result.get("lane", "uncertain")
    stats["lane_chosen"] = lane

    if lane == "form":
        image, report = _process_form_lane(...)
    elif lane == "card":
        image, report = _process_card_like_lane(..., lane_name="card")
    else:
        image, report = _process_card_like_lane(..., lane_name="uncertain")

    report["router"] = router_result
    report["stats"] = stats
    report["mask_counts"] = _report_mask_counts(report)
    return image, report
```

---

## 4) Router Script (How Form vs Card Is Chosen)

### 4.1 OCR-lite pre-step

Pseudo-script from `core/ocr/paddle.py::run_ocr_lite_for_routing`:

```python
def run_ocr_lite_for_routing(image, max_tokens=30, ocr):
    # Aggressive resize for speed
    if max(height, width) > ROUTER_OCR_LITE_MAX_SIDE:  # default 800
        image = resize(image)

    # Use shared PaddleOCR singleton
    results = ocr.ocr(image)
    adapted = adapt_paddle_result(results)
    texts, _, _ = get_texts_and_boxes(adapted)

    # Token cap
    return texts[:max_tokens]
```

### 4.2 Lane classification

Pseudo-script from `core/router.py::classify_document_lane`:

```python
def classify_document_lane(ocr_tokens, confidence_threshold=0.55):
    if not ocr_tokens:
        return lane="uncertain", confidence=0.0

    normalized = normalize(" ".join(ocr_tokens))

    # Skip keyword hard route
    for kw in SKIP_KEYWORDS:
        if kw in normalized:
            return lane="form", confidence=1.0, skip_detected=True

    card_count, card_matches = CARD_SIGNALS(ocr_tokens, normalized)
    form_count, form_matches = FORM_SIGNALS(ocr_tokens, normalized)

    total_signals = card_count + form_count
    if total_signals == 0:
        lane = "uncertain"; confidence = 0.0
    elif card_count > form_count * ROUTER_BIAS_RATIO:  # default 1.5
        lane = "card"; confidence = min(1.0, card_count / ROUTER_CARD_CONF_DIVISOR)  # default /5
    elif form_count > card_count * ROUTER_BIAS_RATIO:
        lane = "form"; confidence = min(1.0, form_count / ROUTER_FORM_CONF_DIVISOR)  # default /6
    else:
        lane = "uncertain"; confidence = ROUTER_MIXED_CONFIDENCE  # default 0.3

    # confidence gate
    if lane != "uncertain" and confidence < confidence_threshold:
        lane = "uncertain"

    return lane, confidence, card_signals, form_signals, reasoning
```

Router loop detail:

- `CARD_SIGNALS` checks fixed card keywords in a loop, then regex `\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b`, then compact Aadhaar mention rule.
- `FORM_SIGNALS` checks form keywords in a loop, table indicators count, and token-count rule.

---

## 5) Exact Form-Lane Script (Application Form Image Path)

This is the primary path for your "application form image" when router picks `lane="form"`.

Pseudo-script from `core/pipeline.py::_process_form_lane`:

```python
def _process_form_lane(image, ocr, skip_keywords_enabled=True, debug=False, stats={}):
    # Step F1: doc orientation correction (0/90/180/270 model)
    image, doc_orientation_failed = _correct_doc_orientation(image)

    # Step F2: full-image OCR
    all_texts, all_boxes, all_confidences, ocr_failed = _run_ocr_on_region(image, ocr)

    # Step F3: skip + PAN check
    checks = _verify_skip_pan(
        all_texts,
        skip_keywords_enabled=skip_keywords_enabled,
        aadhaar_confirmed=False
    )

    if checks["skipped"]:
        # No masking performed in this branch
        return image, build_form_skip_report(...)

    # Step F4: build token objects
    tokens_list = []
    for (t, b, c) in zip(all_texts, all_boxes, all_confidences):
        tokens_list.append({"text": t, "coordinates": b, "confidence": c})

    # Step F5: pattern detection over OCR tokens
    detected_words = find_aadhaar_patterns(tokens_list)

    # Step F6: apply black rectangles from detected pattern types
    image = mask_ocr_detections(image, detected_words, tokens_list)

    # Step F7: return report
    return image, build_form_success_report(ocr_patterns_found=len(detected_words), ...)
```

---

## 6) Form-Lane Sub-Script A: `_correct_doc_orientation`

Pseudo-script from `core/pipeline.py`:

```python
def _correct_doc_orientation(image):
    try:
        angle = DocOrientationModel.predict(image)  # returns 0/90/180/270
        if angle == 90:
            return rotate_90_counterclockwise(image), False
        if angle == 180:
            return rotate_180(image), False
        if angle == 270:
            return rotate_90_clockwise(image), False
    except Exception:
        return image, True

    return image, False  # angle 0
```

---

## 7) Form-Lane Sub-Script B: `_run_ocr_on_region`

Pseudo-script from `core/pipeline.py`:

```python
def _run_ocr_on_region(image, ocr, crop_box=None):
    if crop_box is not None:
        # clamp crop to image bounds
        x1, y1, x2, y2 = clamp(crop_box, image.shape)
        if invalid_crop(x1, y1, x2, y2):
            return [], [], [], False
        ocr_region = image[y1:y2, x1:x2]
    else:
        ocr_region = image
        x1, y1 = 0, 0

    ocr_image, scale_to_original = resize_image_for_ocr(ocr_region, max_side=PADDLE_OCR_MAX_SIDE)

    try:
        ocr_results = ocr.ocr(ocr_image)
        if ocr_results and ocr_results[0]:
            adapted = adapt_paddle_result(ocr_results)
            adapted = scale_adapted_ocr_results(adapted, scale_to_original)
        else:
            adapted = []
    except Exception:
        return [], [], [], True

    texts, boxes, confidences = get_texts_and_boxes(adapted)

    if crop_box is not None:
        # Loop: map OCR polygons from crop-space to full-image coordinates
        new_boxes = []
        for box in boxes:
            new_boxes.append([(pt.x + x1, pt.y + y1) for pt in box])
        boxes = new_boxes

    return texts, boxes, confidences, False
```

---

## 8) Form-Lane Sub-Script C: `_verify_skip_pan`

Pseudo-script from `core/pipeline.py` + `core/classifiers.py`:

```python
def _verify_skip_pan(all_texts, skip_keywords_enabled, aadhaar_confirmed):
    combined_text = " ".join(all_texts).lower()

    # Skip-keyword route (only when aadhaar_confirmed=False)
    if skip_keywords_enabled and combined_text and not aadhaar_confirmed:
        # Loop over SKIP_KEYWORDS
        for kw in SKIP_KEYWORDS:
            if kw in combined_text:
                return skipped=True, skip_reason="skip_keywords", skip_keyword=kw, pan_found=False

    # PAN detection (signal score)
    # +2 if "INCOME TAX DEPARTMENT"
    # +2 if "PERMANENT ACCOUNT NUMBER"
    # +1 if PAN regex [A-Z]{5}[0-9]{4}[A-Z]
    # +1 if word-boundary PAN
    # PAN confirmed if score >= 2
    if not aadhaar_confirmed and is_pan_card(all_texts):
        return skipped=True, skip_reason="pan_card", pan_found=True

    return skipped=False
```

---

## 9) Form-Lane Sub-Script D: `find_aadhaar_patterns` (Forensic Loop Detail)

Pseudo-script from `core/ocr/masking.py`:

```python
def find_aadhaar_patterns(tokens_list):
    detected_words = []
    flags = {aadhar_found, cersai_found, crif_found, pmay_found, disb_dt_found, loan_code_found, hw_found}

    # Loop A: pre-scan all tokens to set flags
    for token in tokens_list:
        text = token["text"].lower().strip()
        set flags based on contains("aadhaar"/"aadhar"/"cersai"/"crif"/"pmay")

    if cersai_found:
        return []  # hard stop for pattern masking

    n = len(tokens_list)

    # Loop B: sequential pattern pass
    for i in range(n):
        word = token[i]
        next_word = token[i+1] if i+1<n else ""
        next_next_word = token[i+2] if i+2<n else ""

        update hw flags when "disb dt" and "loan code" cues appear

        # Case 1: single-token 12-digit extraction
        # condition: (aadhar_found or crif_found) and valid Aadhaar
        maybe append type="number"

        # Case 2: two-token 12-digit merge
        # condition: (aadhar_found or crif_found) and is_twelve_digit_number(word+next_word) and valid
        maybe append type="number"

        # Case 3: 4-4-4 split tokens
        # condition: 3 adjacent four-digit tokens, with boundary guard, valid Aadhaar
        maybe append type="number_split"

        # Case 4: "aadhaar card no" pattern
        maybe append type="app_form_var1"

        # Case 5: applicant/spouse + aadhar fuzzy pattern (non-PMAY)
        maybe append type="app_form_var2"

        # Case 6: PMAY additional variants
        maybe append type="aadhaarcard_applicant" or "aadhaar_card_applicant"

        # Case 7: "aadhaar uid/vid" table cue
        maybe append type="aadhaar_uid"

        # Case 8: PMAY handwritten variants
        maybe append type="aadhar_number_pmy_hw" or "aadhar_table_pmy_hw"

    # Loop C (safety pass): if Aadhaar/CRIF keyword absent, still mask valid numbers
    if not (aadhar_found or crif_found):
        for i, token in enumerate(tokens_list):
            check single-token valid 12-digit -> append type="number_safety"
            check two-token combined valid 12-digit -> append type="number_safety"

    return detected_words
```

Validation used in this step:

- `is_valid_aadhaar_number`:
  - exactly 12 digits
  - first digit must be `2-9`
  - per-digit repeat guard inside Verhoeff path
  - Verhoeff checksum pass

---

## 10) Form-Lane Sub-Script E: `mask_ocr_detections` (Forensic Loop Detail)

Pseudo-script from `core/ocr/masking.py`:

```python
def mask_ocr_detections(image, detected_words, tokens_list=None):
    color = black

    # Loop D: for every detected pattern
    for dw in detected_words:
        coords = dw["coordinates"]
        x1, x2, y1, y2 = bbox_from_polygon(coords)
        w = x2 - x1
        h = y2 - y1
        dtype = dw["type"]

        if dtype == "number_split":
            mask rectangle spanning first + second token coordinates

        elif dtype == "number":
            # mask first ~66% width
            x2_mask = x1 + 0.66*w
            draw black rectangle

        elif dtype == "app_form_var1":
            x1_mask = x2 + 1.65*w
            x2_mask = x1_mask + 3.9*w
            draw rectangle

        elif dtype == "app_form_var2":
            x1_mask = x2 + 0.65*w
            x2_mask = x1_mask + 3.75*w
            draw rectangle

        elif dtype == "aadhaar_card_applicant":
            x1_mask = x2 + 1.9*w
            x2_mask = x1_mask + 2.95*w
            y1_mask = y1 - 0.15*h
            y2_mask = y1_mask + 2.20*h
            draw rectangle

        elif dtype == "aadhaarcard_applicant":
            x1_mask = x2 + 1.25*w
            x2_mask = x1_mask + 2.85*w
            y2_mask = y1 + 2.25*h
            draw rectangle

        elif dtype == "aadhar_number_pmy_hw":
            x1_mask = x2 + 1.0*w
            x2_mask = x1_mask + 2.5*w
            draw rectangle

        elif dtype == "aadhaar_uid":
            x1_mask = x1 - 1.08*w
            x2_mask = x1_mask + 2.5*w
            y1_mask = y2 + 1.25*h
            y2_mask = y1_mask + 7.92*h

            # optional loop-assisted table extension
            if tokens_list:
                y2_mask = uid_table_masking_coordinates(..., tokens_list)
            if y2_mask - y1_mask > 5:
                draw rectangle

        elif dtype == "aadhar_table_pmy_hw":
            x1_mask = x1
            x2_mask = x1_mask + 2.5*w
            y1_mask = y2
            y2_mask = y1_mask + 4*h
            if tokens_list:
                y2_mask = uid_table_masking_coordinates(..., tokens_list)
            if abs(y2_mask - y1_mask) > 5:
                draw rectangle

    return image
```

---

## 11) Important Branch Reality for Form Images

Even if a document is visually a form, execution can still go to `uncertain` lane when router confidence is below `0.55`.

In that case it does **not** follow the form-only script above; it runs full card-like flow:

- orientation sweep loop over 8 angles
- gate scoring
- Aadhaar crop loops
- YOLO masking loop
- OCR masking loop

So in production traces, first confirm:

```text
report["lane_chosen"] == "form"
```

before assuming the pure form-lane path.

---

## 12) Card/Uncertain Lane Script (Full Forensic Branch)

Pseudo-script from `core/pipeline.py::_process_card_like_lane`:

```python
def _process_card_like_lane(image, lane_name, ocr, skip_keywords_enabled=True, debug=False, stats={}):
    # C1: orientation + full gate scoring
    image, best_angle, gate_result = find_best_orientation(image, score_fn=run_full_gate_scoring)

    # C2: OCR on card crops (or fallback full-image OCR)
    image, all_texts, all_boxes, all_confidences, ocr_failed, doc_orientation_failed, aadhaar_crops = \
        _run_ocr_for_card_path(image, ocr, gate_result)

    # C3: card text verification
    aadhaar_confirmed = bool(aadhaar_crops) and is_aadhaar_card_confirmed(all_texts)

    # C4: skip + PAN check
    checks = _verify_skip_pan(all_texts, skip_keywords_enabled, aadhaar_confirmed)
    if checks["skipped"]:
        return image, build_card_skip_report(...)

    # C5: optional PVC photo masking loop
    if aadhaar_crops:
        image, pvc_stats = mask_pvc_aadhaar(image, aadhaar_crops)
    else:
        pvc_stats = zeroes

    # C6: YOLO masking loop (number/qr/xx)
    image, yolo_report = mask_yolo_detections(
        image,
        gate_result["merged_dets"],
        debug=debug,
        stats=stats,
        ocr=ocr,
        aadhaar_boxes=gate_result["aadhaar_boxes"],
    )

    # C7: OCR token-pattern masking (same as form lane)
    tokens_list = [{"text": t, "coordinates": b, "confidence": c} for t, b, c in zip(...)]
    detected_words = find_aadhaar_patterns(tokens_list)
    image = mask_ocr_detections(image, detected_words, tokens_list)

    # C8: rotate back to original orientation
    if best_angle != 0:
        inverse_angle = {90: 270, 180: 180, 270: 90}.get(best_angle, 0)
        image = rotate_image(image, inverse_angle)

    return image, build_card_success_report(...)
```

---

## 13) Orientation Loop Script (`find_best_orientation`)

Pseudo-script from `core/utils/angle_detector.py`:

```python
def find_best_orientation(image, score_fn):
    score_0, data_0 = score_fn(image)
    if not ORIENTATION_ENABLED:
        return image, 0, data_0

    # Early exit check uses:
    # strong_aadhaar = max_aadhaar_conf >= ORIENTATION_STRONG_THRESHOLD (default 0.75)
    # strong_target = best_number_conf >= 0.7 OR best_qr_conf >= 0.7
    if composite_early_exit(data_0):
        return image, 0, data_0

    scored_cache = {0: (image, score_0, data_0)}

    hint_angle = doc_orientation_hint(image)  # 0/90/180/270
    if hint_angle != 0 and hint_angle in ORIENTATION_ANGLES:
        hint_rotated = rotate(hint_angle)
        hint_score, hint_data = score_fn(hint_rotated)
        scored_cache[hint_angle] = (...)
        if composite_early_exit(hint_data):
            return hint_rotated, hint_angle, hint_data

    best_angle, best_score, best_image, best_data = 0, score_0, image, data_0

    # Loop E: try each configured angle
    for angle in ORIENTATION_ANGLES:  # default [0,45,90,135,180,225,270,315]
        if angle in scored_cache:
            rotated, score, data = scored_cache[angle]
        else:
            rotated = rotate(angle)  # cardinal via cv2.rotate, diagonal via affine
            score, data = score_fn(rotated)

        if composite_early_exit(data):
            return rotated, angle, data

        if score > best_score:
            best_score, best_angle, best_image, best_data = score, angle, rotated, data

    return best_image, best_angle, best_data
```

---

## 14) Gate Scoring Loop Script (`run_full_gate_scoring`)

Pseudo-script from `core/aadhaar_gate.py`:

```python
def run_full_gate_scoring(rotated_image):
    # G1: preprocess once
    grey, preprocessed = preprocess_greyscale(rotated_image)

    # G2: main.pt inference on preprocessed greyscale-as-BGR
    main_dets = yolo_main(preprocessed_bgr)

    # G3: front/back filter
    fb_filtered = detect_aadhaar_side(grey, main_dets.coordinates, main_dets.labels, main_dets.confs, return_metadata=True)

    aadhaar_confs = [d.conf for d in fb_filtered if d.label == "aadhaar"]
    max_aadhaar_conf = max(aadhaar_confs) if exists else 0.0

    # G4: score formula
    if aadhaar_confs:
        score = max_aadhaar_conf + min(len(aadhaar_confs), 3)*0.05 + 0.1
    else:
        raw = [d.conf for d in main_dets if d.label == "aadhaar"]
        if raw:
            score = max(raw) * 0.5
        else:
            score = len(main_dets) * 0.01

    aadhaar_dets = [d for d in fb_filtered if d.label == "aadhaar"]
    aadhaar_boxes = [d.box for d in aadhaar_dets]

    if aadhaar_boxes:
        all_merged = []
        aadhaar_crops = []

        # Loop F: per-Aadhaar-card crop loop
        for aadhaar_det in aadhaar_dets:
            crop = clamp_and_extract(rotated_image, aadhaar_det.box)
            best_crop_dets = yolo_best(crop)              # best.pt on crop
            best_full = map_crop_dets_to_full(best_crop_dets, crop_box)
            main_inside = filter_dets_inside_box(fb_filtered, crop_box)
            merged_inside = merge_detections(main_inside, best_full)
            all_merged.extend(merged_inside)
            aadhaar_crops.append(crop_info_with_fb_metadata)

        # Loop G: add non-Aadhaar dets not inside crop boxes
        for det in fb_filtered:
            if det.label == "aadhaar":
                continue
            if not inside_any_crop_box(det):
                all_merged.append(det)
    else:
        best_full = yolo_best(rotated_image)  # full-image fallback
        all_merged = merge_detections(fb_filtered, best_full)
        aadhaar_crops = []

    best_number_conf = max(conf for det in all_merged if "number" in det.label and det.model == "best")
    best_qr_conf = max(conf for det in all_merged if "qr" in det.label and det.model == "best")

    return score, {
        "merged_dets": all_merged,
        "aadhaar_boxes": aadhaar_boxes,
        "aadhaar_crops": aadhaar_crops,
        "fb_confirmed": len(aadhaar_confs) > 0,
        "max_aadhaar_conf": max_aadhaar_conf,
        "best_number_conf": best_number_conf_or_0,
        "best_qr_conf": best_qr_conf_or_0,
    }
```

---

## 15) OCR-on-Card-Crops Loop Script (`_run_ocr_for_card_path`)

Pseudo-script from `core/pipeline.py`:

```python
def _run_ocr_for_card_path(image, ocr, gate_result):
    all_texts, all_boxes, all_confidences = [], [], []
    ocr_failed = False
    doc_orientation_failed = False

    aadhaar_crops = gate_result.get("aadhaar_crops", [])

    if aadhaar_crops:
        # Loop H: OCR each crop
        for crop_info in aadhaar_crops:
            texts, boxes, confs, failed = _run_ocr_on_region(image, ocr, crop_box=crop_info["crop_box"])
            if failed:
                ocr_failed = True
            all_texts.extend(texts)
            all_boxes.extend(boxes)
            all_confidences.extend(confs)
    else:
        image, doc_orientation_failed = _correct_doc_orientation(image)
        all_texts, all_boxes, all_confidences, ocr_failed = _run_ocr_on_region(image, ocr)

    return image, all_texts, all_boxes, all_confidences, ocr_failed, doc_orientation_failed, aadhaar_crops
```

---

## 16) YOLO Masking Loop Script (`mask_yolo_detections`)

Pseudo-script from `core/ocr/masking.py`:

```python
def mask_yolo_detections(image, merged_detections, ocr, aadhaar_boxes):
    report = {"is_number":0, "is_number_masked":0, "is_qr":0, "is_qr_masked":0, "is_xx":0}

    # Loop I: iterate all merged detections
    for det in merged_detections:
        label = det.label.lower()
        conf = det.conf
        box = det.box

        if "qr" in label and conf > 0.3:
            report["is_qr"] += 1
            if "masked" not in label:
                # spatial guard
                if aadhaar_boxes and is_inside_aadhaar_by_area(box, aadhaar_boxes):
                    draw_black_rect(box)
                    report["is_qr_masked"] += 1

        elif "number" in label and conf > 0.3:
            report["is_number"] += 1
            if "masked" not in label and "xx" not in label:
                already_masked = check_image_text(image, box, det.label, ocr=ocr)  # OCR check x/y/k
                if not already_masked:
                    image, ocr_success = _ocr_verify_and_mask_number(image, box, det.label, ocr)
                    if not ocr_success:
                        mask_region = compute_digit_mask_region(box)  # fallback
                        draw_black_rect(mask_region)
                    report["is_number_masked"] += 1
                else:
                    report["is_xx"] += 1

        elif "xx" in label:
            report["is_xx"] += 1

    return image, report
```

---

## 17) Optional Alternate Entrypoints (for completeness)

### 17.1 PDF inside masking-engine

`_mask_pdf` loop structure:

```python
while start_page <= end_page:
    pages = convert_from_path(pdf, first_page=start_page, last_page=chunk_end)
    for page in pages:
        save page as jpg
        report = MASK_SINGLE_IMAGE(jpg_path)  # same flow as above
        page_reports[page_no] = report
```

Then rebuild PDF from masked page JPGs.

### 17.2 Batch processor service

`services/batch-processor/batch.py` calls the same `core.pipeline.process_image` per page/image, then aggregates `page_reports` into DynamoDB fields.

---

## 18) Forensic Checkpoints to Log/Inspect

When validating a form-image run end-to-end, inspect these in order:

1. Router tokens and lane decision (`tokens`, `lane`, `confidence`, `reasoning`)
2. `lane_chosen` in final report
3. `skipped`, `skip_reason`, `pan_found`
4. `ocr_failed`, `doc_orientation_failed`
5. `ocr_patterns_found`
6. `mask_counts` summary
7. Final output image artifact after masking
