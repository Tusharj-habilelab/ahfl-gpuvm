"""
log_writer.py — DynamoDB logging helpers for AHFL-Masking 1.1

Shared functions for writing and querying masking results in DynamoDB.
Used by batch-processor and reporting scripts.

Table schema:
  PK:     DOC#<file_path>
  SK:     ISO timestamp (createdAt)
  GSI1PK: STATUS#<PENDING|PROCESSING|COMPLETED|ERROR>
  GSI1SK: ISO timestamp
"""

import logging
import uuid
import math
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Dict, Set

from boto3.dynamodb.conditions import Attr

from .database import get_dynamo_table

log = logging.getLogger(__name__)


def _to_decimal(v):
    """Convert float to Decimal for DynamoDB; guard NaN/Inf."""
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return Decimal(0)
        return Decimal(str(v))
    return v


def write_mask_log(record: dict, table=None) -> bool:
    """
    Insert a single masking result record into DynamoDB.

    Args:
        record: Dictionary with at minimum {file_path, status}.
        table: DynamoDB Table resource (will connect if None).

    Returns:
        True if successful, False otherwise.
    """
    try:
        if table is None:
            table = get_dynamo_table()

        now = datetime.now(timezone.utc).isoformat()
        item = {
            "PK": f"DOC#{record.get('file_path', 'unknown')}",
            "SK": now,
            "id": str(uuid.uuid4()),
            "status": record.get("status", "COMPLETED"),
            "GSI1PK": f"STATUS#{record.get('status', 'COMPLETED')}",
            "GSI1SK": now,
            "createdAt": now,
            "updatedAt": now,
        }
        # Add all other fields from record, converting floats
        for k, v in record.items():
            if k not in ("status",):
                item[k] = _to_decimal(v) if isinstance(v, float) else v

        table.put_item(Item=item)
        return True
    except Exception as e:
        log.error(f"Failed to log record: {e}")
        return False


def bulk_write_logs(records: List[Dict], table=None) -> tuple:
    """
    Batch insert multiple records into DynamoDB.

    Args:
        records: List of record dicts (each must have file_path).
        table: DynamoDB Table resource (will connect if None).

    Returns:
        Tuple (successful_count, failed_count).
    """
    if not records:
        return 0, 0

    try:
        if table is None:
            table = get_dynamo_table()

        successful = 0
        failed = 0

        for record in records:
            if write_mask_log(record, table=table):
                successful += 1
            else:
                failed += 1

        log.info(f"Batch log completed: {successful} inserted, {failed} failed")
        return successful, failed
    except Exception as e:
        log.error(f"Batch operation failed: {e}")
        return 0, len(records)


def get_processed_paths(table=None) -> Set[str]:
    """
    Return file paths already COMPLETED or exhausted retries (to avoid re-processing).

    Args:
        table: DynamoDB Table resource (will connect if None).

    Returns:
        Set of file paths already processed.
    """
    if table is None:
        table = get_dynamo_table()

    skip = set()
    scan_kwargs = {
        "FilterExpression": (
            Attr("status").eq("COMPLETED") |
            (Attr("status").eq("ERROR") & Attr("retryAttempts").gte(3))
        ),
        "ProjectionExpression": "file_path",
    }
    try:
        while True:
            response = table.scan(**scan_kwargs)
            for item in response.get("Items", []):
                if "file_path" in item:
                    skip.add(item["file_path"])
            if "LastEvaluatedKey" not in response:
                break
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    except Exception as e:
        log.error(f"Could not fetch processed paths: {e}")
        raise

    return skip


def ensure_log_table() -> None:
    """
    Validate that the DynamoDB table exists and is accessible.
    Raises RuntimeError if table cannot be reached.

    Note: DynamoDB tables are created via AWS Console/CloudFormation/Terraform,
    not programmatically from application code. This function only validates access.
    """
    get_dynamo_table()  # raises RuntimeError if table doesn't exist
    log.info("DynamoDB table validated")
