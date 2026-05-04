"""
export_logs.py — Export DynamoDB processed records to CSV.

Usage:
    python scripts/reporting/export_logs.py [--status COMPLETED] [--output results.csv]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import csv
import argparse
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Attr

from core import get_dynamo_table, TABLE_NAME

load_dotenv()


def export_to_csv(status_filter: str = None, output_file: str = None):
    """Scan DynamoDB table and export to CSV."""
    table = get_dynamo_table()

    scan_kwargs = {
        "ProjectionExpression": (
            "file_path, #st, is_aadhaar, is_number, is_number_masked, "
            "is_QR, is_QR_masked, is_XX, ocr_patterns_found, "
            "totalPages, scannedPages, maskedPages, createdAt, updatedAt"
        ),
        "ExpressionAttributeNames": {"#st": "status"},
    }

    if status_filter:
        scan_kwargs["FilterExpression"] = Attr("status").eq(status_filter)

    items = []
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    if not items:
        print("[!] No records found.")
        return

    if output_file is None:
        output_file = f"{TABLE_NAME}_export.csv"

    headers = [
        "file_path", "status", "is_aadhaar", "is_number", "is_number_masked",
        "is_QR", "is_QR_masked", "is_XX", "ocr_patterns_found",
        "totalPages", "scannedPages", "maskedPages", "createdAt", "updatedAt",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(items)

    print(f"[OK] Exported {len(items)} records to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export DynamoDB logs to CSV.")
    parser.add_argument("--status", type=str, default=None,
                        help="Filter by status (COMPLETED, ERROR, PROCESSING)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV filename")
    args = parser.parse_args()
    export_to_csv(status_filter=args.status, output_file=args.output)
