"""
scripts/check_dynamo_table.py — Validate DynamoDB table schema against batch.py requirements.

Checks:
  1. Table exists and is ACTIVE
  2. PK attribute (HASH key) named "PK"
  3. SK attribute (RANGE key) named "SK"
  4. GSI1 index exists with GSI1PK (HASH) and GSI1SK (RANGE)
  5. BillingMode is PAY_PER_REQUEST

Usage:
  python scripts/check_dynamo_table.py
  python scripts/check_dynamo_table.py --table aadhar-masking-metadata-table --region ap-south-1
"""

import argparse
import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

DEFAULT_TABLE = os.environ.get("TABLE_NAME", "ahfl_processed_data")
DEFAULT_REGION = os.environ.get("AWS_REGION", "ap-south-1")

PASS = "[PASS]"
FAIL = "[FAIL]"


def check_table(table_name: str, region: str) -> bool:
    dynamodb = boto3.client("dynamodb", region_name=region)

    print(f"\nChecking table '{table_name}' in {region} ...\n")

    try:
        resp = dynamodb.describe_table(TableName=table_name)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ResourceNotFoundException":
            print(f"{FAIL} Table '{table_name}' does not exist.")
        else:
            print(f"{FAIL} {code}: {e.response['Error']['Message']}")
        return False

    table = resp["Table"]
    failures = 0

    # 1. Table status
    status = table.get("TableStatus")
    if status == "ACTIVE":
        print(f"{PASS} TableStatus = ACTIVE")
    else:
        print(f"{FAIL} TableStatus = {status} (expected ACTIVE)")
        failures += 1

    # 2. Key schema
    key_schema = {k["AttributeName"]: k["KeyType"] for k in table.get("KeySchema", [])}

    if key_schema.get("PK") == "HASH":
        print(f"{PASS} PK (HASH key) named 'PK'")
    else:
        actual = list(key_schema.keys())
        print(f"{FAIL} PK (HASH key) missing or wrong — found keys: {actual}")
        print(f"       batch.py writes: PK = 'DOC#s3://bucket/key'")
        failures += 1

    if key_schema.get("SK") == "RANGE":
        print(f"{PASS} SK (RANGE key) named 'SK'")
    else:
        print(f"{FAIL} SK (RANGE key) missing — table has no sort key")
        print(f"       batch.py writes: SK = ISO-8601 timestamp")
        failures += 1

    # 3. GSI1
    gsi_list = table.get("GlobalSecondaryIndexes") or []
    gsi1 = next((g for g in gsi_list if g["IndexName"] == "GSI1"), None)

    if gsi1 is None:
        print(f"{FAIL} GSI1 index missing")
        print(f"       batch.py queries: GSI1PK = 'STATUS#COMPLETED' to build skip list")
        failures += 1
    else:
        gsi1_keys = {k["AttributeName"]: k["KeyType"] for k in gsi1.get("KeySchema", [])}
        gsi1_status = gsi1.get("IndexStatus", "UNKNOWN")

        if gsi1_keys.get("GSI1PK") == "HASH" and gsi1_keys.get("GSI1SK") == "RANGE":
            print(f"{PASS} GSI1 exists with GSI1PK (HASH) + GSI1SK (RANGE), status={gsi1_status}")
        else:
            print(f"{FAIL} GSI1 exists but wrong keys — found: {gsi1_keys}")
            failures += 1

    # 4. BillingMode
    billing = (table.get("BillingModeSummary") or {}).get("BillingMode", "PROVISIONED")
    if billing == "PAY_PER_REQUEST":
        print(f"{PASS} BillingMode = PAY_PER_REQUEST")
    else:
        print(f"{FAIL} BillingMode = {billing} (expected PAY_PER_REQUEST)")
        failures += 1

    # Summary
    print()
    if failures == 0:
        print("RESULT: PASS — table schema matches batch.py requirements.")
    else:
        print(f"RESULT: FAIL — {failures} issue(s) found. Table cannot be used as-is.")
        print()
        print("Required schema for a new table:")
        print(f"  PK  (HASH)   = 'DOC#{{s3_file_path}}'")
        print(f"  SK  (RANGE)  = ISO-8601 timestamp")
        print(f"  GSI1: GSI1PK (HASH) + GSI1SK (RANGE), ProjectionType=ALL")
        print(f"  BillingMode  = PAY_PER_REQUEST")

    return failures == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check DynamoDB table schema for batch.py compatibility")
    parser.add_argument("--table",  default=DEFAULT_TABLE,  help="Table name")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    args = parser.parse_args()

    ok = check_table(args.table, args.region)
    sys.exit(0 if ok else 1)
