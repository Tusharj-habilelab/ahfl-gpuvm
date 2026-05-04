# Migrated from: unique_ (AHFL-Masking 1.0)
# Role: DB utility to fetch distinct processed file paths.
#        Updated for DynamoDB status-workflow schema (batch-processor 1.1).
"""
utils/ — DynamoDB query helpers for the batch processor.
"""

import os
from boto3.dynamodb.conditions import Attr
from core import get_dynamo_table

TABLE_NAME = os.environ.get("TABLE_NAME", "ahfl_processed_data")
MAX_RETRY_ATTEMPTS = 3


def get_completed_paths() -> set:
    """Return file paths with COMPLETED status (safe to skip re-processing)."""
    table = get_dynamo_table()
    completed = set()
    scan_kwargs = {
        "FilterExpression": Attr("status").eq("COMPLETED"),
        "ProjectionExpression": "file_path",
    }
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            if "file_path" in item:
                completed.add(item["file_path"])
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return completed


def get_failed_paths(max_retries: int = MAX_RETRY_ATTEMPTS) -> dict:
    """
    Return file_path → retryAttempts for ERROR items with retries exhausted.
    Useful for reporting/monitoring.
    """
    table = get_dynamo_table()
    failed = {}
    scan_kwargs = {
        "FilterExpression": (
            Attr("status").eq("ERROR") & Attr("retryAttempts").gte(max_retries)
        ),
        "ProjectionExpression": "file_path, retryAttempts, errorMessage",
    }
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            if "file_path" in item:
                failed[item["file_path"]] = {
                    "retryAttempts": int(item.get("retryAttempts", 0)),
                    "errorMessage": item.get("errorMessage", ""),
                }
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return failed
