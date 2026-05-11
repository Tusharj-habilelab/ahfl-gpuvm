"""
database.py — DynamoDB helpers for AHFL-Masking 1.1.

get_dynamo_table() — DynamoDB Table resource for batch-processor.
                     Auth via EC2 IAM role — no credentials needed.

Schema:
  PK:     DOC#<file_path>
  SK:     ISO timestamp (createdAt)
  GSI1PK: STATUS#<PENDING|PROCESSING|COMPLETED|ERROR>
  GSI1SK: ISO timestamp
"""

import os
import logging
import boto3
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("TABLE_NAME", "ahfl_processed_data")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")


DEFAULT_MASK_COUNTS = {
    "is_aadhaar": 0,
    "is_number": 0,
    "is_number_masked": 0,
    "is_qr": 0,
    "is_qr_masked": 0,
    "is_xx": 0,
    "ocr_patterns_found": 0,
}


def build_default_record(pk: str, sk: str, file_path: str, s3_key: str = "") -> dict:
    """Build base DynamoDB record with backward-compatible + new schema fields."""
    return {
        "PK": pk,
        "SK": sk,
        "file_path": file_path,
        "s3_key": s3_key,
        "status": "PENDING",
        "retryAttempts": 0,
        "totalPages": 0,
        "scannedPages": 0,
        "maskedPages": 0,
        "is_aadhaar": 0,
        "is_number": 0,
        "is_number_masked": 0,
        "is_QR": 0,
        "is_QR_masked": 0,
        "is_XX": 0,
        "ocr_patterns_found": 0,
        "mask_counts": dict(DEFAULT_MASK_COUNTS),
        "lane_chosen": "unknown",
        "orientation_hint_angle": None,
        "final_winning_angle": None,
        "skip_reason": None,
        "card_detected": False,
        "aadhaar_verified": False,
        "pan_found": False,
        "pageReports": {},
        "GSI1PK": "STATUS#PENDING",
        "GSI1SK": sk,
        "createdAt": sk,
        "updatedAt": sk,
    }


def get_dynamo_table(table_name: str = None):
    """
    Return a DynamoDB Table resource or raise on failure.
    Auth via EC2 IAM role — no credentials needed on the GPU VM.

    Args:
        table_name: Override table name (defaults to TABLE_NAME env var).

    Usage:
        table = get_dynamo_table()
        table.put_item(Item={...})
    """
    name = table_name or TABLE_NAME
    try:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(name)
        table.load()  # validates table exists; raises ClientError if not found
        log.info(f"DynamoDB: connected to table '{name}' in {AWS_REGION}")
        return table
    except Exception as err:
        raise RuntimeError(f"[DB] DynamoDB connection failed: {err}") from err
