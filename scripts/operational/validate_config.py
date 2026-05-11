"""
validate_config.py — Pre-deployment configuration validator for AHFL-Masking 1.1

Checks:
  1. GPU availability (CUDA device count, memory)
  2. S3 bucket access (RAW_BUCKET + MASKED_BUCKET)
  3. DynamoDB table existence
  4. Model file paths (all 4 .pt files)
  5. PaddleOCR GPU flag

Usage:
    python scripts/operational/validate_config.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PASS = "✓"
FAIL = "✗"
WARN = "!"

results = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    icon = PASS if ok else FAIL
    msg = f"  [{icon}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append(ok)
    return ok


print("\n=== AHFL-Masking 1.1 Config Validation ===\n")

# ── 1. GPU ────────────────────────────────────────────────────────────────────
print("1. GPU")
try:
    import torch
    cuda_ok = torch.cuda.is_available()
    device_count = torch.cuda.device_count() if cuda_ok else 0
    check("CUDA available", cuda_ok, f"{device_count} device(s)" if cuda_ok else "torch.cuda.is_available() = False")
    if cuda_ok:
        for i in range(device_count):
            props = torch.cuda.get_device_properties(i)
            mem_gb = props.total_memory / 1024**3
            check(f"  GPU {i}: {props.name}", True, f"{mem_gb:.1f} GB")
    gpu_enabled = os.environ.get("GPU_ENABLED", "true").lower() == "true"
    check("GPU_ENABLED env var", gpu_enabled, f"GPU_ENABLED={os.environ.get('GPU_ENABLED', 'true')}")
except ImportError:
    check("torch import", False, "pip install torch")

# ── 2. S3 ─────────────────────────────────────────────────────────────────────
print("\n2. S3 Buckets")
try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError

    raw_bucket = os.environ.get("RAW_BUCKET", "ahfl-ams-raw-data-bucket-333813598364-ap-south-1-an")
    masked_bucket = os.environ.get("MASKED_BUCKET", "ahfl-uat-ams-masked-data-bucket-333813598364-ap-south-1-an")
    s3 = boto3.client("s3", config=BotoConfig(connect_timeout=5, retries={"max_attempts": 1}))

    for label, bucket in [("RAW_BUCKET", raw_bucket), ("MASKED_BUCKET", masked_bucket)]:
        try:
            s3.head_bucket(Bucket=bucket)
            check(f"{label}: {bucket}", True)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            check(f"{label}: {bucket}", False, f"ClientError [{code}]")
        except Exception as e:
            check(f"{label}: {bucket}", False, str(e))
except ImportError:
    check("boto3 import", False, "pip install boto3")

# ── 3. DynamoDB ────────────────────────────────────────────────────────────────
print("\n3. DynamoDB")
try:
    import boto3
    table_name = os.environ.get("TABLE_NAME", "ahfl_processed_data")
    region = os.environ.get("AWS_REGION", "ap-south-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)
    table.load()
    check(f"Table '{table_name}'", True, f"status={table.table_status}")
except Exception as e:
    check(f"Table '{os.environ.get('TABLE_NAME', 'ahfl_processed_data')}'", False, str(e))

# ── 4. Model Files ─────────────────────────────────────────────────────────────
print("\n4. Model Files")
models = {
    "MODEL_MAIN": os.environ.get("MODEL_MAIN", "/app/models/main.pt"),
    "MODEL_BEST": os.environ.get("MODEL_BEST", "/app/models/best.pt"),
    "MODEL_FRONT_BACK": os.environ.get("MODEL_FRONT_BACK", "/app/models/front_back_detect.pt"),
    "MODEL_YOLO_N": os.environ.get("MODEL_YOLO_N", "/app/models/yolov8n.pt"),
}
for env_key, path in models.items():
    exists = Path(path).exists()
    check(f"{env_key}: {path}", exists, "" if exists else "FILE NOT FOUND")

# ── 5. PaddleOCR ──────────────────────────────────────────────────────────────
print("\n5. PaddleOCR")
try:
    from paddleocr import PaddleOCR
    check("paddleocr importable", True)
    paddle_dir = os.environ.get("PADDLE_MODEL_DIR", "/app/models/paddleocr")
    check(
        f"PADDLE_MODEL_DIR: {paddle_dir}",
        Path(paddle_dir).exists(),
        "" if Path(paddle_dir).exists() else "directory missing (auto-downloads on first run)",
    )
except ImportError:
    check("paddleocr import", False, "pip install paddleocr")

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n=== Summary ===")
passed = sum(results)
total = len(results)
failed = total - passed
print(f"  Passed: {passed}/{total}")
if failed:
    print(f"  Failed: {failed} — fix above before deploying")
    sys.exit(1)
else:
    print("  All checks passed — ready to deploy")
