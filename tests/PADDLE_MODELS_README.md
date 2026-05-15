# PaddleOCR Models Testing Guide

## Models Overview

Your application uses **5 PaddleOCR models**:

### 1. PP-OCRv5_server_det (Text Detection)
- **Purpose**: Finds text regions in images
- **Output**: Bounding box coordinates for each text region
- **Usage**: First stage of OCR pipeline
- **Location**: `official_models/PP-OCRv5_server_det/`

### 2. en_PP-OCRv5_mobile_rec (Text Recognition)
- **Purpose**: Reads text from detected regions
- **Output**: Text strings + confidence scores
- **Usage**: Second stage of OCR pipeline
- **Location**: `official_models/en_PP-OCRv5_mobile_rec/`

### 3. PP-LCNet_x1_0_textline_ori (Text Line Orientation)
- **Purpose**: Detects if text lines are upside down (0° or 180°)
- **Output**: Orientation angle for each text line
- **Usage**: Automatically used when `use_textline_orientation=True`
- **Location**: `official_models/PP-LCNet_x1_0_textline_ori/`

### 4. PP-LCNet_x1_0_doc_ori (Document Orientation)
- **Purpose**: Detects whole document rotation (0°/90°/180°/270°)
- **Output**: Document angle + confidence score
- **Usage**: Used in `core/utils/angle_detector.py` for orientation correction
- **Location**: `official_models/PP-LCNet_x1_0_doc_ori/`
- **How it helps**: Automatically rotates Aadhaar cards that are scanned sideways or upside down

### 5. UVDoc (Document Unwarping)
- **Purpose**: Straightens curved/warped documents
- **Output**: Flattened document image
- **Usage**: Optional preprocessing for curved documents
- **Location**: `official_models/UVDoc/`

## How Models Are Used in Your Application

```python
# In core/ocr/paddle.py
def create_paddle_ocr():
    ocr = PaddleOCR(
        lang="en",
        use_textline_orientation=True,  # Uses model #3
        device="gpu:0",
    )
    return ocr

# In core/ocr/paddle.py
def get_doc_orientation_model():
    doc_ori = DocImgOrientationClassification(
        device="gpu:0"  # Uses model #4
    )
    return doc_ori
```

### Pipeline Flow:
1. **Document Orientation Detection** (Model #4)
   - Detects if document is rotated
   - Rotates to correct orientation
   
2. **Text Detection** (Model #1)
   - Finds all text regions
   
3. **Text Line Orientation** (Model #3)
   - Checks if individual text lines are upside down
   
4. **Text Recognition** (Model #2)
   - Reads text from each region
   
5. **Aadhaar Pattern Matching**
   - Finds 12-digit Aadhaar numbers
   - Applies masking

## Testing

### Run Visual Test Script
```bash
# Test with a real Aadhaar card image
python scripts/test_paddle_models.py --image /path/to/aadhaar.jpg --output ./test_results

# This will create 6 output images showing:
# 1. Detection boxes
# 2. Recognition results
# 3. Text line orientation correction
# 4. Document orientation correction
# 5. UVDoc unwarping (if applicable)
# 6. Full pipeline with Aadhaar detection
```

### Run Unit Tests
```bash
# Run all unit tests
pytest tests/test_paddle_models_unit.py -v

# Run specific model test
pytest tests/test_paddle_models_unit.py::TestDocOrientationModel -v

# Run with coverage
pytest tests/test_paddle_models_unit.py --cov=core.ocr -v
```

## Orientation Model Benefits

The **PP-LCNet_x1_0_doc_ori** model helps your application by:

1. **Auto-correcting rotated scans**: If someone scans an Aadhaar card sideways (90° or 270°), it automatically rotates it upright
2. **Handling upside-down documents**: Detects 180° rotation and flips the image
3. **Improving OCR accuracy**: OCR works best on upright text, so orientation correction improves text recognition
4. **Reducing manual intervention**: No need for users to manually rotate images

### Example Usage in Your Code:
```python
# In core/utils/angle_detector.py
from core.ocr.paddle import get_doc_orientation_model

doc_ori = get_doc_orientation_model()
result = doc_ori(image)

if result['angle'] == 90:
    image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
elif result['angle'] == 180:
    image = cv2.rotate(image, cv2.ROTATE_180)
elif result['angle'] == 270:
    image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
```

## Model Performance

| Model | Size | Inference Time (CPU) | Inference Time (GPU) |
|-------|------|---------------------|---------------------|
| PP-OCRv5_server_det | ~47MB | ~200ms | ~20ms |
| en_PP-OCRv5_mobile_rec | ~10MB | ~50ms | ~5ms |
| PP-LCNet_x1_0_textline_ori | ~7MB | ~5ms | ~1ms |
| PP-LCNet_x1_0_doc_ori | ~7MB | ~3ms | ~1ms |
| UVDoc | ~150MB | ~500ms | ~50ms |

## Troubleshooting

### Models not loading?
```bash
# Check model directory
ls -la ~/.paddlex/official_models/

# Or check your custom path
echo $PADDLE_MODEL_DIR
```

### GPU not being used?
```python
import paddle
print(f"CUDA available: {paddle.is_compiled_with_cuda()}")
print(f"GPU count: {paddle.device.cuda.device_count()}")
```

### Low accuracy?
- Ensure images are high resolution (min 1000px on longest side)
- Check if orientation correction is enabled
- Verify text is clear and not blurry
- Consider preprocessing (contrast enhancement, denoising)
