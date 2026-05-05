# D4 PATCHES FOR GPU MASTER SYNC
# Instructions: Append these patches to GPU_MASTER_SYNC.py before the REPORT section (line 651)

# ─────────────────────────────────────────────────────────────────
# D4 PATCH SECTION — Append to GPU_MASTER_SYNC.py
# Add these patches BEFORE the REPORT section
# ─────────────────────────────────────────────────────────────────

# PATCH D4.1: core/ocr/paddle.py — GPU device hardcoding
patch(
    "D4.1 — paddle.py: GPU device hardcoded (remove CPU fallback)",
    "core/ocr/paddle.py",
    """def create_paddle_ocr() -> PaddleOCR:
    \"\"\"
    Build a PaddleOCR instance for Aadhaar text extraction (PaddleOCR 3.4.0+).
    Models are auto-downloaded to /root/.paddlex on first call and cached permanently.
    GPU mode imports from core.config — single source of truth for GPU_ENABLED default.
    \"\"\"
    # Import here to avoid circular imports (paddle.py is imported by core/pipeline.py)
    from core.config import GPU_ENABLED as _use_gpu, PADDLE_MODEL_DIR as _model_dir
    return PaddleOCR(
        lang="en",
        use_textline_orientation=True,
        device="gpu:0" if _use_gpu else "cpu",
        det_model_dir=os.path.join(_model_dir, "det"),
        rec_model_dir=os.path.join(_model_dir, "rec"),
        cls_model_dir=os.path.join(_model_dir, "cls"),
    )""",
    """def create_paddle_ocr() -> PaddleOCR:
    \"\"\"
    Build a PaddleOCR instance for Aadhaar text extraction (PaddleOCR 3.4.0+).
    Models loaded from PADDLE_MODEL_DIR/{det,rec,cls} (volume-mounted, no auto-download).
    \"\"\"
    from core.config import PADDLE_MODEL_DIR as _model_dir
    return PaddleOCR(
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
