"""
scripts/create_dynamo_table.py — One-time setup: create ahfl_processed_data DynamoDB table.

Schema:
  PK  = "DOC#{file_path}"      (Partition key)
  SK  = ISO-8601 timestamp     (Sort key — supports retry history per file)

GSI1 (query by processing status):
  GSI1PK = "STATUS#{status}"   (PENDING / PROCESSING / COMPLETED / ERROR)
  GSI1SK = ISO-8601 timestamp

Usage:
  python scripts/create_dynamo_table.py
  python scripts/create_dynamo_table.py --table my-custom-table --region us-east-1
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


def create_table(table_name: str, region: str) -> None:
    dynamodb = boto3.client("dynamodb", region_name=region)

    try:
        dynamodb.describe_table(TableName=table_name)
        print(f"[SKIP] Table '{table_name}' already exists in {region}.")
        return
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    print(f"[CREATE] Creating table '{table_name}' in {region} ...")
    dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK",     "AttributeType": "S"},
            {"AttributeName": "SK",     "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    waiter = dynamodb.get_waiter("table_exists")
    print("[WAIT] Waiting for table to become ACTIVE ...")
    waiter.wait(TableName=table_name, WaiterConfig={"Delay": 5, "MaxAttempts": 20})
    print(f"[OK] Table '{table_name}' is ACTIVE.")
    print()
    print("IAM policy required on the EC2 role:")
    print(f"  dynamodb:PutItem, UpdateItem, Scan on arn:aws:dynamodb:{region}:*:table/{table_name}")
    print(f"  dynamodb:Query on arn:aws:dynamodb:{region}:*:table/{table_name}/index/GSI1")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create ahfl_processed_data DynamoDB table")
    parser.add_argument("--table",  default=DEFAULT_TABLE,  help="Table name")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    args = parser.parse_args()

    try:
        create_table(args.table, args.region)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
