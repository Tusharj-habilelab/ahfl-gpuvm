# Application Logging Overview

## Logging Levels & What's Logged

### INFO (Normal Operations — Always Visible)
- GPU memory fraction initialization
- Signal handling (shutdown)
- DynamoDB write checkpoints
- Model preload status: PaddleOCR, YOLO Main, YOLO Best, front/back classifier
- GPU warmup completion
- DynamoDB connection & skip path counts
- Source directory & file statistics
- File processing status: [SKIP] already processed, [DRY-RUN] would process
- File processing result: [OK] or [FAIL]
- Path keyword skip detection
- S3 bucket accessibility
- S3 listing & file count
- Batch completion & record count
- YOLO model loading & device placement
- PDF conversion & reconstruction
- Output directory creation
- DynamoDB table validation

### WARNING (Non-Fatal, Recoverable)
- DynamoDB unavailable fallback
- DynamoDB write failures (pre-write, skip-write, update, completed-write)
- Password-protected PDF files
- PDF chunk processing failures
- Page extraction errors
- DynamoDB retry attempts
- Stale PROCESSING record cleanup (records older than threshold hours)
- GPU warmup skipped
- C2 FIX: CERSAI keyword detected — masking skipped
- C3 FIX: Valid Aadhaar number masked despite missing keyword (OCR corruption)
- pytesseract unavailable for OCR-lite routing
- OCR-lite routing failures
- PVC person detection failures
- OCR bbox normalization failures
- Confidence score parsing failures
- File size validation failures
- doc_orientation correction failures

### ERROR (Failures — Data Loss Risk)
- [FAIL] File processing error with exception message
- DynamoDB error-write failures (audit trail)
- ZIP extraction/processing errors
- S3 upload failures with HTTP status code
- Stale record reset failures
- YOLO model loading failures
- YOLO inference failures
- run_ocr_lite_for_routing failures
- OCR processing errors
- DynamoDB batch operation failures
- DynamoDB record fetch failures
- pdf2image/img2pdf library not installed
- PDF conversion failures

### DEBUG (Only with --debug Flag)
- Router classification decision: lane, confidence, card_signals, form_signals, reasoning
- Skip keyword detection
- Orientation scoring per angle (0°/90°/180°/270°)
- doc_orientation model failures
- YOLO detection log: [model] label conf=X box=[x1,y1,x2,y2]
- QR skipping reasons (no/outside Aadhaar bbox)
- PVC person masking coordinates
- Malformed detection skipping
- File keyword skip detection
- S3 download completion
- ZIP extraction/re-zipping completion

## Logging Gaps (Not Currently Logged)

- Lane choice decision (form vs card) at INFO level
- _correct_doc_orientation actual angle result
- Aadhaar verification confirmed/rejected outcome
- Per-file timing stats at INFO (only in report dict)
- Router confidence threshold boundary cases
- Gate scoring breakdown per angle
- OCR-lite token count at INFO level
- YOLO detection count per type (before masking)

## Log Sources (Total: ~135 statements)

| File | Count | Focus |
|------|-------|-------|
| batch.py | 88 | Batch processing lifecycle, S3 ops, DynamoDB |
| yolo_runner.py | 11 | Model loading/inference |
| file_utils.py | 8 | PDF/file operations |
| angle_detector.py | 5 | Orientation computation |
| masking.py | 5 | C2/C3 fixes, detection logging |
| log_writer.py | 4 | DynamoDB operations |
| paddle.py | 4 | Routing OCR failures |
| classifiers.py | 3 | PVC masking |
| ocr_adapter.py | 3 | Bbox/confidence parsing |
| router.py | 2 | Router debug |
| pipeline.py | 2 | OCR errors |

---

Generated: 2026-05-04
