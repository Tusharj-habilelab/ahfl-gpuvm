# Database module for AHFL-Masking 1.1 (DynamoDB only)
from .database import get_dynamo_table
from .log_writer import write_mask_log

__all__ = ["get_dynamo_table", "write_mask_log"]
