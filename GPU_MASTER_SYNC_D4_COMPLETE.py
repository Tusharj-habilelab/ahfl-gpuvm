#!/usr/bin/env python3
"""
Master GPU Sync Script — Applies ALL local fixes to GPU VM
Run this on GPU VM terminal (copy-paste entire script)
GPU path: /data-disk/ahfl_deploy_gpu/

D4 COMPLETE VERSION: Includes patches 1-12 (original) + D4.1-D4.3 (D4 GPU fixes)
"""

import os, sys

BASE = "/data-disk/ahfl_deploy_gpu"
applied = []
failed = []

def patch(label, path, old, new):
    full = os.path.join(BASE, path)
    try:
        with open(full, 'r') as f:
            content = f.read()
        if old in content:
            with open(full, 'w') as f:
                f.write(content.replace(old, new, 1))
            applied.append(f"✓ {label}")
        elif new in content:
            applied.append(f"✓ {label} (already applied)")
        else:
            failed.append(f"✗ {label} — pattern not found in {path}")
    except FileNotFoundError:
        failed.append(f"✗ {label} — FILE NOT FOUND: {full}")
    except Exception as e:
        failed.append(f"✗ {label} — {e}")

def append_after(label, path, marker, insertion):
    full = os.path.join(BASE, path)
    try:
        with open(full, 'r') as f:
            content = f.read()
        if insertion.strip() in content:
            applied.append(f"✓ {label} (already applied)")
            return
        if marker in content:
            content = content.replace(marker, marker + insertion, 1)
            with open(full, 'w') as f:
                f.write(content)
            applied.append(f"✓ {label}")
        else:
            failed.append(f"✗ {label} — marker not found in {path}")
    except FileNotFoundError:
        failed.append(f"✗ {label} — FILE NOT FOUND: {full}")
    except Exception as e:
        failed.append(f"✗ {label} — {e}")

def write_file(label, path, content):
    full = os.path.join(BASE, path)
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w') as f:
            f.write(content)
        applied.append(f"✓ {label}")
    except Exception as e:
        failed.append(f"✗ {label} — {e}")

# ─────────────────────────────────────────────────────────────────
# PATCH 1: core/ocr/paddle.py — Wire PADDLE_MODEL_DIR
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 1 — paddle.py: PADDLE_MODEL_DIR wired",
    "core/ocr/paddle.py",
    """    from core.config import GPU_ENABLED as _use_gpu
    return PaddleOCR(lang="en", use_textline_orientation=True, use_gpu=_use_gpu)""",
    """    from core.config import GPU_ENABLED as _use_gpu, PADDLE_MODEL_DIR as _model_dir
    return PaddleOCR(
        lang="en",
        use_textline_orientation=True,
        device="gpu:0",
        det_model_dir=os.path.join(_model_dir, "det"),
        rec_model_dir=os.path.join(_model_dir, "rec"),
        cls_model_dir=os.path.join(_model_dir, "cls"),
    )"""
)

# ─────────────────────────────────────────────────────────────────
# PATCH 2: core/utils/file_utils.py — Force RGB conversion
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 2 — file_utils.py: Force RGB conversion",
    "core/utils/file_utils.py",
    '            page.save(img_path, "JPEG")',
    '            page.convert(\'RGB\').save(img_path, "JPEG")  # Force RGB (3 channels for YOLO)'
)

# ─────────────────────────────────────────────────────────────────
# PATCH 3: core/config.py — Add validate_required_env_vars()
# ─────────────────────────────────────────────────────────────────
VALIDATE_FUNC = '''

def validate_required_env_vars() -> None:
    """Raise RuntimeError if required env vars are missing at startup."""
    required = ["TABLE_NAME", "AWS_REGION", "RAW_BUCKET", "MASKED_BUCKET"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Set them in docker-compose.yml or environment."
        )

'''
append_after(
    "PATCH 3 — config.py: validate_required_env_vars()",
    "core/config.py",
    'PADDLE_MODEL_DIR = os.environ.get("PADDLE_MODEL_DIR", "models/paddleocr")',
    VALIDATE_FUNC
)

# ─────────────────────────────────────────────────────────────────
# PATCH 4a: core/classifiers.py — Add logging import + logger
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 4a — classifiers.py: logging import",
    "core/classifiers.py",
    "import threading\n",
    "import threading\nimport logging\n"
)
patch(
    "PATCH 4b — classifiers.py: log + _person_model vars",
    "core/classifiers.py",
    '_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"',
    '_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"\n\nlog = logging.getLogger(__name__)\n\n_person_model = None\n_person_model_lock = threading.Lock()'
)

# ─────────────────────────────────────────────────────────────────
# PATCH 4c: core/classifiers.py — Add _get_person_model + mask_pvc_aadhaar
# FIX: patch() prepends functions BEFORE last return of is_aadhaar_card_confirmed
#      (append_after with partial function signature would have corrupted the code)
# ─────────────────────────────────────────────────────────────────
PVC_FUNCTIONS = '''

def _get_person_model():
    """Lazy-load yolov8n for person detection on PVC Aadhaar cards."""
    global _person_model
    if _person_model is None:
        with _person_model_lock:
            if _person_model is None:
                model_path = os.environ.get("MODEL_YOLO_N", "models/yolov8n.pt")
                _person_model = YOLO(model_path).to(_DEVICE)
    return _person_model


def mask_pvc_aadhaar(image, aadhaar_crops):
    """Mask person photos on PVC Aadhaar cards. Returns (image, stats_dict)."""
    if not aadhaar_crops:
        return image, {"pvc_cards_processed": 0, "pvc_cards_masked": 0}

    person_model = _get_person_model()
    h, w = image.shape[:2]
    pvc_cards_processed = 0
    pvc_cards_masked = 0

    for crop_info in aadhaar_crops:
        crop_box = crop_info.get("crop_box")
        if crop_box is None:
            continue
        pvc_cards_processed += 1
        x1, y1, x2, y2 = map(int, crop_box)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue

        aadhaar_region = image[y1:y2, x1:x2]
        person_coordinates = []
        num_rotations = 0

        while num_rotations < 2 and len(person_coordinates) != 2:
            blurred = cv2.GaussianBlur(aadhaar_region, (3, 3), 0)
            try:
                results = person_model(blurred)
                for result in results:
                    if result.boxes is not None:
                        for box in result.boxes:
                            if int(box.cls[0]) == 0 and float(box.conf[0]) >= 0.2:
                                person_coordinates.append(box.xyxy[0].tolist())
            except Exception as e:
                log.warning(f"PVC masking person detection failed: {e}")
                break
            if len(person_coordinates) == 2:
                break
            aadhaar_region = cv2.rotate(aadhaar_region, cv2.ROTATE_90_CLOCKWISE)
            num_rotations += 1

        if len(person_coordinates) == 2:
            px11, py11, px12, py12 = map(int, person_coordinates[0])
            px21, py21, px22, py22 = map(int, person_coordinates[1])
            area1 = abs(px12 - px11) * abs(py12 - py11)
            area2 = abs(px22 - px21) * abs(py22 - py21)
            if area1 > area2:
                px22 = int(px22 + ((px22 - px21) / 10))
                py22 = int(py22 + ((py22 - py21) / 10))
                cv2.rectangle(aadhaar_region, (px21, py21), (px22, py22), (0, 0, 0), -1)
                log.debug(f"PVC: masked person at ({px21},{py21})-({px22},{py22})")
            else:
                px12 = int(px12 + ((px12 - px11) / 10))
                py12 = int(py12 + ((py12 - py11) / 10))
                cv2.rectangle(aadhaar_region, (px11, py11), (px12, py12), (0, 0, 0), -1)
                log.debug(f"PVC: masked person at ({px11},{py11})-({px12},{py12})")
            if num_rotations == 1:
                aadhaar_region = cv2.rotate(aadhaar_region, cv2.ROTATE_90_COUNTERCLOCKWISE)
            image[y1:y2, x1:x2] = aadhaar_region
            pvc_cards_masked += 1

    return image, {"pvc_cards_processed": pvc_cards_processed, "pvc_cards_masked": pvc_cards_masked}

'''
_AADHAAR_END = '    if "YOUR AADHAAR NO" in combined_upper:\n        return True\n    return False'
patch(
    "PATCH 4c — classifiers.py: _get_person_model + mask_pvc_aadhaar",
    "core/classifiers.py",
    _AADHAAR_END,
    _AADHAAR_END + "\n" + PVC_FUNCTIONS
)

# ─────────────────────────────────────────────────────────────────
# PATCH 5: core/pipeline.py — PVC masking integration
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 5a — pipeline.py: import mask_pvc_aadhaar",
    "core/pipeline.py",
    "from core.classifiers import is_pan_card, is_aadhaar_card_confirmed",
    "from core.classifiers import is_pan_card, is_aadhaar_card_confirmed, mask_pvc_aadhaar"
)
patch(
    "PATCH 5b — pipeline.py: PVC masking stage 2a.5",
    "core/pipeline.py",
    "        # 2b. PaddleOCR Pass",
    """        # 2a.5: PVC Aadhaar photo masking
        aadhaar_crops = gate_result.get("aadhaar_crops", [])
        pvc_stats = {"pvc_cards_processed": 0, "pvc_cards_masked": 0}
        if aadhaar_crops:
            image, pvc_stats = mask_pvc_aadhaar(image, aadhaar_crops)

        # 2b. PaddleOCR Pass"""
)
# FIX: old pattern now uses **yolo_report context (previous pattern "ocr_failed:\n}" didn't
#      exist — pipeline.py always has doc_orientation_failed after ocr_failed)
patch(
    "PATCH 5c — pipeline.py: pvc_stats in report",
    "core/pipeline.py",
    '            **yolo_report,\n            "ocr_patterns_found": len(detected_words),',
    '            **yolo_report,\n            **pvc_stats,\n            "ocr_patterns_found": len(detected_words),'
)

# ─────────────────────────────────────────────────────────────────
# PATCH 6: services/batch-processor/batch.py
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 6a — batch.py: zipfile import",
    "services/batch-processor/batch.py",
    "import shutil\n",
    "import shutil\nimport zipfile\n"
)
# FIX: old was "from core.config import (" — that line doesn't exist.
#      Actual line is "from core.config import COMMIT_BATCH_SIZE, GPU_ENABLED"
patch(
    "PATCH 6b — batch.py: validate_required_env_vars import",
    "services/batch-processor/batch.py",
    "from core.config import COMMIT_BATCH_SIZE, GPU_ENABLED",
    "from core.config import validate_required_env_vars\nfrom core.config import COMMIT_BATCH_SIZE, GPU_ENABLED"
)
UNZIP_FUNCTIONS = '''
# Archive extraction
def _unzip(file_path: str, extract_to: str) -> bool:
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        log.debug(f"Extracted ZIP: {file_path}")
        return True
    except Exception as e:
        log.error(f"Error extracting ZIP {file_path}: {e}")
        shutil.rmtree(extract_to, ignore_errors=True)
        return False


def _extract_path(path_name: str, s3_mode: bool = False) -> None:
    for root, dirs, files in os.walk(path_name):
        for file in files:
            filepath = os.path.join(root, file)
            if file.endswith(('.zip', '.ZIP')):
                temp_dir = os.path.join(root, f"zip_{os.path.splitext(file)[0]}")
                os.makedirs(temp_dir, exist_ok=True)
                if not _unzip(filepath, temp_dir):
                    continue
                try:
                    _extract_path(temp_dir, s3_mode=s3_mode)
                    if s3_mode:
                        os.remove(filepath)
                    else:
                        os.remove(filepath)
                        shutil.make_archive(os.path.splitext(filepath)[0], 'zip', temp_dir)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    log.error(f"Error processing ZIP {filepath}: {e}")
                    shutil.rmtree(temp_dir, ignore_errors=True)


'''
# FIX: was append_after("def _process_image(", ...) which would inject code INSIDE
#      the function signature. Now uses patch() to prepend UNZIP_FUNCTIONS before def.
patch(
    "PATCH 6c — batch.py: _unzip + _extract_path",
    "services/batch-processor/batch.py",
    "def _process_image(",
    UNZIP_FUNCTIONS + "def _process_image("
)
patch(
    "PATCH 6d — batch.py: MAX_S3_FILE_SIZE 100MB → 15MB",
    "services/batch-processor/batch.py",
    "str(100 * 1024 * 1024)",
    "str(15 * 1024 * 1024)"
)
# FIX: was log.info("Starting AHFL batch processor") which doesn't exist.
#      validate_required_env_vars() goes at top of __main__ block, before argparse.
patch(
    "PATCH 6e — batch.py: validate_required_env_vars at startup",
    "services/batch-processor/batch.py",
    'if __name__ == "__main__":\n    parser = argparse.ArgumentParser(',
    'if __name__ == "__main__":\n    # Validate required env vars at startup (fail fast)\n    validate_required_env_vars()\n\n    parser = argparse.ArgumentParser('
)

# ─────────────────────────────────────────────────────────────────
# PATCH 7: services/batch-processor/Dockerfile (full rewrite)
# ─────────────────────────────────────────────────────────────────
BATCH_DOCKERFILE = """FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

LABEL service="batch-processor" version="1.1.0"

ARG CUDA_HOME=/usr/local/cuda
ENV CUDA_HOME=${CUDA_HOME} \\
    PATH=${CUDA_HOME}/bin:${PATH} \\
    LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH} \\
    PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \\
    python3.10 \\
    python3-pip \\
    python3-dev \\
    build-essential \\
    git \\
    wget \\
    pkg-config \\
    libopenblas-dev \\
    liblapack-dev \\
    gfortran \\
    libgomp1 \\
    libglib2.0-0 \\
    libsm6 \\
    libxext6 \\
    libxrender-dev \\
    libgl1-mesa-glx \\
    tesseract-ocr \\
    poppler-utils \\
    ca-certificates \\
    && update-ca-certificates \\
    && rm -rf /var/lib/apt/lists/* \\
    && ln -s /usr/bin/python3 /usr/bin/python

RUN pip install --upgrade --no-cache-dir pip setuptools wheel

# PaddlePaddle GPU — cu121 = correct ABI for CUDA 12.2 host
RUN pip install --no-cache-dir \\
    paddlepaddle-gpu==3.3.0 \\
    -i https://www.paddlepaddle.org.cn/packages/stable/cu121/

# PyTorch GPU
RUN pip install --no-cache-dir \\
    torch==2.1.2+cu121 \\
    torchvision==0.16.2+cu121 \\
    --index-url https://download.pytorch.org/whl/cu121

COPY services/batch-processor/requirements.txt .
RUN pip install --no-cache-dir \\
    -r requirements.txt \\
    --extra-index-url https://pypi.org/simple

COPY services/batch-processor/ .
COPY core/ ./core/

ENV CUDA_VISIBLE_DEVICES=0 \\
    TF_FORCE_GPU_ALLOW_GROWTH=true \\
    CUDA_LAUNCH_BLOCKING=0

VOLUME ["/app/models"]

# Run as root — avoids permission issues with mounted volumes on closed GPU VM.

ENTRYPOINT ["python", "batch.py"]
CMD ["--s3"]
"""
write_file("PATCH 7 — batch-processor/Dockerfile (full rewrite)", "services/batch-processor/Dockerfile", BATCH_DOCKERFILE)

# ─────────────────────────────────────────────────────────────────
# PATCH 8: masking-engine/Dockerfile — root + workers 1
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 8 — masking-engine/Dockerfile: root + workers 1",
    "services/masking-engine/Dockerfile",
    'RUN groupadd -r appuser && useradd -r -g appuser appuser \\\n    && chown -R appuser:appuser /app\nUSER appuser\n\nCMD ["uvicorn", "engine:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]',
    '# Run as root in this closed GPU VM deployment to avoid permission issues.\n# One worker: GPU models load once, not duplicated.\nCMD ["uvicorn", "engine:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]'
)

# ─────────────────────────────────────────────────────────────────
# PATCH 9: docker-compose.yml — paddleocr_cache → bind mounts
# FIX: original PATCH 9a only replaced FIRST occurrence (masking-engine).
#      Added PATCH 9c to fix batch-processor volumes separately.
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 9a — docker-compose.yml: masking-engine paddleocr_cache → bind mount",
    "docker-compose.yml",
    "      - paddleocr_cache:/root/.paddlex",
    "      - /ahfl-models/.paddlex:/root/.paddlex"
)
# PATCH 9c: batch-processor volumes — remove masked_output + /ahfl-source-data, fix paddleocr_cache
patch(
    "PATCH 9c — docker-compose.yml: batch-processor volumes cleanup",
    "docker-compose.yml",
    "      - /ahfl-models:/app/models:ro\n      - masked_output:/app/output/masked\n      - /ahfl-source-data:/app/source:ro\n      - paddleocr_cache:/root/.paddlex",
    "      - /ahfl-models:/app/models:ro\n      - /ahfl-models/.paddlex:/root/.paddlex"
)
patch(
    "PATCH 9b — docker-compose.yml: remove paddleocr_cache named volume def",
    "docker-compose.yml",
    "  paddleocr_cache:\n    driver: local\n",
    ""
)

# ─────────────────────────────────────────────────────────────────
# CRITICAL SECURITY FIXES: C1, C2, C3
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# PATCH 10: C1 FIX — is_pan_card() multi-signal approach
# Issue: Bare "PAN" substring matches applicant names (Pankaj, Pandey)
# Fix: Require 2+ signals: INCOME TAX DEPARTMENT, PERMANENT ACCOUNT NUMBER,
#      PAN regex, word-boundary PAN
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 10 — C1 FIX: is_pan_card() multi-signal (prevent name false positives)",
    "core/classifiers.py",
    '''def is_pan_card(ocr_texts: List[str]) -> bool:
    """
    Detect if OCR text indicates a PAN card (not Aadhaar).

    Checks for:
      - "PAN" keyword
      - "Permanent Account" phrase
      - PAN format regex: [A-Z]{5}[0-9]{4}[A-Z]

    Args:
        ocr_texts: List of OCR-extracted text strings.

    Returns:
        True if PAN card indicators found.
    """
    combined = " ".join(ocr_texts)
    combined_upper = combined.upper()

    if "INCOME TAX DEPARTMENT" in combined_upper:
        return True

    if "PAN" in combined_upper or "PERMANENT ACCOUNT" in combined_upper:
        return True

    if _PAN_PATTERN.search(combined_upper):
        return True

    return False''',
    '''def is_pan_card(ocr_texts: List[str]) -> bool:
    """
    Detect if OCR text indicates a PAN card (not Aadhaar).

    Multi-signal approach to avoid false positives from names like Pankaj/Pandey:
    Requires 2+ signals from:
      - INCOME TAX DEPARTMENT keyword (2 points)
      - PERMANENT ACCOUNT NUMBER phrase (2 points)
      - PAN regex pattern: [A-Z]{5}[0-9]{4}[A-Z] (1 point)
      - Word-boundary "PAN" match (1 point)

    Threshold: 2+ signals required to confirm PAN card.

    Args:
        ocr_texts: List of OCR-extracted text strings.

    Returns:
        True if 2+ PAN indicators found.
    """
    combined = " ".join(ocr_texts)
    combined_upper = combined.upper()

    signal_count = 0

    if "INCOME TAX DEPARTMENT" in combined_upper:
        signal_count += 2

    if "PERMANENT ACCOUNT NUMBER" in combined_upper:
        signal_count += 2

    if _PAN_PATTERN.search(combined_upper):
        signal_count += 1

    if re.search(r'\\bPAN\\b', combined_upper):
        signal_count += 1

    return signal_count >= 2'''
)

# ─────────────────────────────────────────────────────────────────
# PATCH 11: C2 FIX — cersai_found explicit logging
# Issue: When CERSAI detected, empty list returned but report shows skipped=False
# Fix: Add logging to audit trail when CERSAI skips masking
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 11 — C2 FIX: cersai_found explicit logging",
    "core/ocr/masking.py",
    """    if cersai_found:
        return detected_words

    n = len(tokens_list)""",
    """    if cersai_found:
        log.info("C2 FIX: CERSAI keyword detected — skipping masking, report should show skip_reason=cersai_found")
        return detected_words

    n = len(tokens_list)"""
)

# ─────────────────────────────────────────────────────────────────
# PATCH 12: C3 FIX — unconditional Verhoeff safety pass
# Issue: aadhar_found gate blocks ALL number masking if OCR corrupts keyword
# Fix: Add unconditional safety pass at end: any 12-digit Verhoeff-valid number
#      masked regardless of keyword match, with warning log (form lane only)
# ─────────────────────────────────────────────────────────────────
patch(
    "PATCH 12 — C3 FIX: unconditional Verhoeff safety pass",
    "core/ocr/masking.py",
    """                        "type": "aadhar_table_pmy_hw"
                        })

    return detected_words""",
    """                        "type": "aadhar_table_pmy_hw"
                        })

    # C3 FIX: Unconditional Verhoeff safety pass
    # If aadhar_found/crif_found is False (keyword corrupted by OCR), still mask valid 12-digit numbers.
    # Form lane only — card lane has YOLO fallback protection.
    if not (aadhar_found or crif_found):
        for i, token in enumerate(tokens_list):
            word = token["text"]
            if is_twelve_digit_number(word):
                cleaned = re.sub(r'[^0-9]', '', word)
                if len(cleaned) == 12 and is_valid_aadhaar_number(cleaned):
                    log.warning(f"C3 FIX: Valid Aadhaar number masked despite missing keyword (OCR corruption?): {cleaned}")
                    detected_words.append({
                        "text": cleaned,
                        "coordinates": token["coordinates"],
                        "type": "number_safety"
                    })

            if i + 1 < len(tokens_list):
                next_word = tokens_list[i + 1]["text"]
                combined = word + next_word
                if is_twelve_digit_number(combined):
                    cleaned = re.sub(r'[^0-9]', '', combined)
                    if len(cleaned) == 12 and is_valid_aadhaar_number(cleaned):
                        log.warning(f"C3 FIX: Valid Aadhaar number masked despite missing keyword (OCR corruption?): {cleaned}")
                        left_coords = token["coordinates"]
                        right_coords = tokens_list[i + 1]["coordinates"]
                        coordinates = [
                            (left_coords[0][0], left_coords[0][1]),
                            (right_coords[1][0], right_coords[1][1]),
                            (right_coords[2][0], right_coords[2][1]),
                            (left_coords[3][0], left_coords[3][1])
                        ]
                        detected_words.append({
                            "text": cleaned,
                            "coordinates": coordinates,
                            "type": "number_safety"
                        })

    return detected_words"""
)

# ─────────────────────────────────────────────────────────────────
# D4 PATCH SECTION — GPU Consistency & S3 Optimization
# ─────────────────────────────────────────────────────────────────

# PATCH D4.1: core/ocr/paddle.py — GPU device hardcoding (use_gpu → device)
patch(
    "D4.1 — paddle.py: GPU device hardcoded (use_gpu → device=gpu:0)",
    "core/ocr/paddle.py",
    """    return PaddleOCR(
        lang="en",
        use_textline_orientation=True,
        use_gpu=_use_gpu,
        det_model_dir=os.path.join(_model_dir, "det"),
        rec_model_dir=os.path.join(_model_dir, "rec"),
        cls_model_dir=os.path.join(_model_dir, "cls"),
    )""",
    """    return PaddleOCR(
        lang="en",
        use_textline_orientation=True,
        device="gpu:0",
        det_model_dir=os.path.join(_model_dir, "det"),
        rec_model_dir=os.path.join(_model_dir, "rec"),
        cls_model_dir=os.path.join(_model_dir, "cls"),
    )"""
)

# PATCH D4.2: core/ocr/paddle.py — Doc orientation model GPU + path
patch(
    "D4.2 — paddle.py: DocImgOrientationClassification GPU device + model path",
    "core/ocr/paddle.py",
    """def get_doc_orientation_model() -> DocImgOrientationClassification:
    \"\"\"
    Lazy-load shared DocImgOrientationClassification instance.

    Model: PP-LCNet_x1_0_doc_ori (7MB, ~3ms CPU inference).
    Predicts whole-document rotation: 0 / 90 / 180 / 270 degrees.
    Auto-downloaded to /root/.paddlex on first call and cached permanently.
    \"\"\"
    global _doc_ori_model
    if _doc_ori_model is None:
        with _doc_ori_lock:
            if _doc_ori_model is None:
                _doc_ori_model = DocImgOrientationClassification()
    return _doc_ori_model""",
    """def get_doc_orientation_model() -> DocImgOrientationClassification:
    \"\"\"
    Lazy-load shared DocImgOrientationClassification instance.

    Model: PP-LCNet_x1_0_doc_ori (7MB, ~3ms inference).
    Predicts whole-document rotation: 0 / 90 / 180 / 270 degrees.
    Loaded from PADDLE_MODEL_DIR/doc_orientation (same volume mount as det/rec/cls).
    \"\"\"
    global _doc_ori_model
    if _doc_ori_model is None:
        with _doc_ori_lock:
            if _doc_ori_model is None:
                from core.config import PADDLE_MODEL_DIR as _model_dir
                _doc_ori_model = DocImgOrientationClassification(
                    model_dir=os.path.join(_model_dir, "doc_orientation"),
                    device="gpu:0",
                )
    return _doc_ori_model"""
)

# PATCH D4.3: services/batch-processor/batch.py — S3 upload simplification
patch(
    "D4.3 — batch.py: S3 upload direct (no staging copy/delete)",
    "services/batch-processor/batch.py",
    """                # Upload — staging key first, then copy to final on success
                staging_key = f"_staging/{uuid.uuid4()}/{s3_key}"
                try:
                    s3.upload_file(upload_path, MASKED_BUCKET, staging_key)
                    s3.copy_object(
                        Bucket=MASKED_BUCKET,
                        CopySource={"Bucket": MASKED_BUCKET, "Key": staging_key},
                        Key=s3_key,
                    )
                    s3.delete_object(Bucket=MASKED_BUCKET, Key=staging_key)
                    log.debug(f"Uploaded → s3://{MASKED_BUCKET}/{s3_key}")""",
    """                # Upload directly to final key in MASKED_BUCKET.
                # No S3 staging object is created, copied, or deleted.
                try:
                    s3.upload_file(upload_path, MASKED_BUCKET, s3_key)
                    log.debug(f"Uploaded → s3://{MASKED_BUCKET}/{s3_key}")"""
)

# ─────────────────────────────────────────────────────────────────
# LOGS PATCH SECTION — Container Logging
# ─────────────────────────────────────────────────────────────────

# PATCH LOGS.1: docker-compose.yml — masking-engine logs volume
patch(
    "PATCH LOGS.1 — docker-compose.yml: masking-engine logs mount",
    "docker-compose.yml",
    "      - /ahfl-models/.paddlex:/root/.paddlex\n    restart: unless-stopped",
    "      - /ahfl-models/.paddlex:/root/.paddlex\n      - ./logs:/logs\n    restart: unless-stopped"
)

# PATCH LOGS.2: docker-compose.yml — batch-processor logs volume
patch(
    "PATCH LOGS.2 — docker-compose.yml: batch-processor logs mount",
    "docker-compose.yml",
    "      - /ahfl-models/.paddlex:/root/.paddlex\n    profiles:\n      - batch",
    "      - /ahfl-models/.paddlex:/root/.paddlex\n      - ./logs:/logs\n    profiles:\n      - batch"
)

# ─────────────────────────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("GPU MASTER SYNC PATCH REPORT")
print("=" * 60)
for msg in applied:
    print(msg)
if failed:
    print()
    for msg in failed:
        print(msg)
print()
print(f"Applied: {len(applied)} | Failed: {len(failed)}")
print("=" * 60)
if not failed:
    print("✅ ALL PATCHES APPLIED (17 total: 12 original + 3 D4 + 2 LOGS)")
    print("   Patches: PADDLE_MODEL_DIR, RGB, validation, PVC masking, pipeline")
    print("   Security: C1 (PAN), C2 (CERSAI), C3 (Verhoeff)")
    print("   GPU: D4.1 (paddle gpu), D4.2 (orientation gpu), D4.3 (S3 direct)")
    print("   Logs: LOGS.1 (masking-engine), LOGS.2 (batch-processor)")
    print("   → docker build -t ahfl-batch-processor:d4 services/batch-processor/")
    print("   → docker build -t ahfl-masking-engine:d4 services/masking-engine/")
    print("   → Run tests: see D4_GPU_DEPLOYMENT_TEST.md")
else:
    print("❌ SOME PATCHES FAILED — check paths above and retry")
print("=" * 60)
