# GPU VM Sync Patches — Copy-Paste Instructions

**Date:** 2026-05-01  
**Access Method:** Web browser (no SSH)  
**Total Patches:** 2 critical files  

---

## IDENTIFIED MISSING FIXES

✗ PATCH 1: `core/ocr/paddle.py` — Missing PADDLE_MODEL_DIR wiring  
✗ PATCH 2: `core/utils/file_utils.py` — Missing RGB conversion  

These 2 fixes caused your dry-run failures.

---

## PATCH 1: core/ocr/paddle.py — Wire PADDLE_MODEL_DIR

**File Path:** `/data-disk/ahfl_deploy_gpu/core/ocr/paddle.py`

**Problem:** Models download to `/root/.paddlex` (default) instead of `/app/models/paddleocr` (volume mount).

**Line 33-34 BEFORE:**
```python
    from core.config import GPU_ENABLED as _use_gpu
    return PaddleOCR(lang="en", use_textline_orientation=True, use_gpu=_use_gpu)
```

**Line 33-41 AFTER:**
```python
    from core.config import GPU_ENABLED as _use_gpu, PADDLE_MODEL_DIR as _model_dir
    return PaddleOCR(
        lang="en",
        use_textline_orientation=True,
        use_gpu=_use_gpu,
        det_model_dir=os.path.join(_model_dir, "det"),
        rec_model_dir=os.path.join(_model_dir, "rec"),
        cls_model_dir=os.path.join(_model_dir, "cls"),
    )
```

---

## PATCH 2: core/utils/file_utils.py — Force RGB Conversion

**File Path:** `/data-disk/ahfl_deploy_gpu/core/utils/file_utils.py`

**Problem:** Grayscale PDFs saved as 1-channel → YOLO expects 3-channel RGB → crashes.

**Line 45 BEFORE:**
```python
            page.save(img_path, "JPEG")
```

**Line 45 AFTER:**
```python
            page.convert('RGB').save(img_path, "JPEG")  # Force RGB (3 channels for YOLO)
```

---

## HOW TO SYNC (No SSH needed)

### Option A: Master Python Script (Recommended)

Copy-paste this ENTIRE script into GPU VM terminal:

```bash
python3 << 'MASTER_PATCH'
import os

patches = []
failures = []

# PATCH 1: paddle.py
try:
    path = "/data-disk/ahfl_deploy_gpu/core/ocr/paddle.py"
    with open(path, 'r') as f:
        content = f.read()
    
    old = """    from core.config import GPU_ENABLED as _use_gpu
    return PaddleOCR(lang="en", use_textline_orientation=True, use_gpu=_use_gpu)"""
    
    new = """    from core.config import GPU_ENABLED as _use_gpu, PADDLE_MODEL_DIR as _model_dir
    return PaddleOCR(
        lang="en",
        use_textline_orientation=True,
        use_gpu=_use_gpu,
        det_model_dir=os.path.join(_model_dir, "det"),
        rec_model_dir=os.path.join(_model_dir, "rec"),
        cls_model_dir=os.path.join(_model_dir, "cls"),
    )"""
    
    if old in content:
        content = content.replace(old, new)
        with open(path, 'w') as f:
            f.write(content)
        patches.append("✓ paddle.py")
    else:
        failures.append("✗ paddle.py — pattern not found")
except Exception as e:
    failures.append(f"✗ paddle.py — {e}")

# PATCH 2: file_utils.py
try:
    path = "/data-disk/ahfl_deploy_gpu/core/utils/file_utils.py"
    with open(path, 'r') as f:
        content = f.read()
    
    old = """            page.save(img_path, "JPEG")"""
    new = """            page.convert('RGB').save(img_path, "JPEG")  # Force RGB (3 channels for YOLO)"""
    
    if old in content:
        content = content.replace(old, new)
        with open(path, 'w') as f:
            f.write(content)
        patches.append("✓ file_utils.py")
    else:
        failures.append("✗ file_utils.py — pattern not found")
except Exception as e:
    failures.append(f"✗ file_utils.py — {e}")

# Report
print("\n=== GPU SYNC PATCH REPORT ===")
for p in patches:
    print(p)
for f in failures:
    print(f)
print(f"Status: {len(patches)}/2 applied")
print("=" * 30)
MASTER_PATCH
```

### Option B: Manual Edit (Web Browser)

1. Open web browser → File editor on GPU VM
2. Navigate to `/data-disk/ahfl_deploy_gpu/core/ocr/paddle.py`
3. Find line 33-34, replace with AFTER code from PATCH 1
4. Navigate to `/data-disk/ahfl_deploy_gpu/core/utils/file_utils.py`
5. Find line 45, replace with AFTER code from PATCH 2
6. Save both files

---

## VERIFY PATCHES APPLIED

After running script, run this to verify:

```bash
echo "=== Checking paddle.py ===" && grep -n "det_model_dir" /data-disk/ahfl_deploy_gpu/core/ocr/paddle.py || echo "NOT FOUND"
echo "=== Checking file_utils.py ===" && grep -n "convert('RGB')" /data-disk/ahfl_deploy_gpu/core/utils/file_utils.py || echo "NOT FOUND"
```

Expected: Both grep commands return line numbers (patches found).

---

## NEXT: Rebuild & Test

```bash
cd /data-disk/ahfl_deploy_gpu/services/batch-processor

# Rebuild image
docker build -t ahfl-batch-processor:gpu -f Dockerfile .

# Test dry-run
docker run --rm --gpus all --env-file /app/.env \
  -v /data/input:/data/input \
  ahfl-batch-processor:gpu \
  python batch.py --source /data/input/test-small --dest /tmp/dry-out --dry-run
```

Expected: Dry-run completes without RGB or model path errors.
