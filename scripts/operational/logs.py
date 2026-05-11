"""
logs.py — Analyze DynamoDB masking stats for reporting.

Usage:
    python scripts/operational/logs.py <start_time> <end_time>
    python scripts/operational/logs.py "2026-04-01T00:00:00" "2026-04-30T23:59:59"

Outputs a CSV with per-status breakdown: total records, masked records,
unique file paths, Aadhaar detections.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import argparse
import csv
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Attr

from core import get_dynamo_table

load_dotenv()


def analyze_records(start_time: str, end_time: str):
    """
    Scan DynamoDB for records between start_time and end_time.
    Returns aggregated stats.
    """
    table = get_dynamo_table()

    scan_kwargs = {
        "FilterExpression": (
            Attr("createdAt").between(start_time, end_time)
        ),
    }

    items = []
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    if not items:
        return None

    total_rows = len(items)
    unique_paths = len({item.get("file_path", "") for item in items})
    aadhaar_rows = sum(1 for item in items if int(item.get("is_aadhaar", 0)) > 0)
    masked_rows = sum(
        1 for item in items
        if (int(item.get("is_number_masked", 0)) +
            int(item.get("is_QR_masked", 0)) +
            int(item.get("ocr_patterns_found", 0))) > 0
    )
    total_qr_masked = sum(int(item.get("is_QR_masked", 0)) for item in items)
    completed = sum(1 for item in items if item.get("status") == "COMPLETED")
    errors = sum(1 for item in items if item.get("status") == "ERROR")

    return {
        "total_rows": total_rows,
        "unique_file_paths": unique_paths,
        "rows_with_masked_data": masked_rows,
        "aadhaar_detected": aadhaar_rows,
        "total_qr_masked": total_qr_masked,
        "completed": completed,
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze DynamoDB masking stats.")
    parser.add_argument("start_time", type=str,
                        help="Start datetime in ISO format (e.g., '2026-04-01T00:00:00')")
    parser.add_argument("end_time", type=str,
                        help="End datetime in ISO format (e.g., '2026-04-30T23:59:59')")
    args = parser.parse_args()

    result = analyze_records(args.start_time, args.end_time)

    if result is None:
        print("[!] No records found in the given time range.")
        sys.exit(0)

    output_file = "masking_stats.csv"
    with open(output_file, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(result.keys()))
        writer.writeheader()
        writer.writerow(result)

    print(f"\nResults ({args.start_time} -> {args.end_time}):")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print(f"\nWritten to {output_file}")
