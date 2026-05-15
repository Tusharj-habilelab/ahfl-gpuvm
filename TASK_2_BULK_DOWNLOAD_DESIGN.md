# Task 2: Bulk Month Download with Failure Tracking

**Date:** 2026-05-15  
**Status:** Design Phase  
**Mode:** GitHub Copilot Claude Mode (VS Code)

---

## Current S3 Flow Tree

```
python batch.py --s3 [--prefix "092021_1/"]
│
├── validate_required_env_vars()
├── _validate_s3_buckets()          ← head_bucket on RAW + MASKED
├── preload_models()
│
└── run_batch_s3(prefix="", ...)
    │
    ├── get_dynamo_table()           ← SINGLE TABLE: "ahfl_processed_data"
    ├── _get_skip_paths(table)       ← GSI1 query: COMPLETED + ERROR-exhausted
    ├── _cleanup_stale_processing_records(table)
    │
    ├── _list_s3_keys(RAW_BUCKET, prefix)
    │   └── S3 paginator list_objects_v2 → returns ALL matching keys (unbounded)
    │
    └── FOR EACH s3_key in sorted(keys):     ← ONE FILE AT A TIME
        │
        ├─ [SKIP] already in skip_paths set?
        ├─ [SKIP] dry_run?
        ├─ [SKIP] keyword in BATCH_PATH_SKIP_KEYWORDS?
        │         └── writes ERROR record to DB with keyword reason
        │
        ├─ _write_pending(table, pk, sk)
        ├─ _update_to_processing(table, pk, sk)
        │
        └─ with tempfile.TemporaryDirectory():    ← ephemeral, per-file
            ├─ s3.head_object → check ContentLength vs MAX_S3_FILE_SIZE
            │   └── [RAISE ValueError if too large → _update_to_error]
            ├─ s3.download_file(RAW_BUCKET, s3_key, /tmp/xxx/filename)
            ├─ [PDF] _is_password_protected_pdf? → [_update_to_error, skip]
            ├─ _process_pdf / _process_image
            ├─ s3.upload_file → MASKED_BUCKET/s3_key
            └─ _update_to_completed / _update_to_error
               └── tempdir auto-deleted after this block
```

---

## S3 Key Anatomy

```
092021_1  /  092021  /  1  /  Audit_documents  /  00460861  /  2297504  /  doc.pdf
   ↑              ↑       ↑                          ↑              ↑
month_batch    repeat  sub_batch               app_number      attach_id
(strip _N)   (ignored)

MONTH EXTRACTION: "092021_1" → strip _N suffix → "092021"
TABLE NAME: ahfl_processed_data_092021
```

**Month extraction from S3 key:**
```python
import re

def _extract_month_from_key(s3_key: str) -> str:
    """
    "092021_1/092021/1/Audit_documents/..." → "092021"
    "092021_2/..."                          → "092021"  (same table)
    "102021_1/..."                          → "102021"  (different table)
    """
    first_segment = s3_key.split("/")[0]
    return re.sub(r'_\d+$', '', first_segment)
```

---

## DB Schema Changes for Task 2

### New Fields in DynamoDB Record

Add to `core/db/database.py` in `build_default_record()`:

```python
{
    "PK": "DOC#s3://...",
    "SK": "2026-05-15T...",
    "status": "PENDING",                    # existing: PENDING → PROCESSING → COMPLETED/ERROR
    "GSI1PK": "STATUS#PENDING",             # existing
    
    # ── NEW: Download state ──
    "download_status": "QUEUED",            # QUEUED | DOWNLOADED | DOWNLOAD_FAILED | DOWNLOAD_SKIPPED
    "download_timestamp": "2026-05-15T...", # when download was attempted
    "download_error": None,                 # if DOWNLOAD_FAILED: exception message
    "download_skip_reason": None,           # if DOWNLOAD_SKIPPED: "size_exceeded" | "keyword_match" | "password_protected"
    "download_retry_count": 0,              # how many times download was attempted
    "local_staging_path": None,             # path in /tmp/ahfl_staging/{month}/ where file was downloaded
}
```

### New DynamoDB Helper Functions (batch.py)

```python
def _update_download_queued(table, pk: str, sk: str) -> None:
    """Mark file as QUEUED for download (added to batch list)."""
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET download_status = :ds, download_timestamp = :ts, download_retry_count = :zero",
        ExpressionAttributeValues={
            ":ds": "QUEUED",
            ":ts": now,
            ":zero": 0,
        },
    )

def _update_download_successful(table, pk: str, sk: str, local_path: str) -> None:
    """Mark file as DOWNLOADED (in staging dir, ready to process)."""
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET download_status = :ds, download_timestamp = :ts, local_staging_path = :lp",
        ExpressionAttributeValues={
            ":ds": "DOWNLOADED",
            ":ts": now,
            ":lp": local_path,
        },
    )

def _update_download_failed(table, pk: str, sk: str, error_msg: str) -> None:
    """Mark file as DOWNLOAD_FAILED with error reason."""
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression=(
            "SET download_status = :ds, download_timestamp = :ts, "
            "download_error = :err ADD download_retry_count :one"
        ),
        ExpressionAttributeValues={
            ":ds": "DOWNLOAD_FAILED",
            ":ts": now,
            ":err": error_msg[:500],
            ":one": 1,
        },
    )

def _update_download_skipped(table, pk: str, sk: str, skip_reason: str) -> None:
    """Mark file as DOWNLOAD_SKIPPED with reason (size, keyword, etc.)."""
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET download_status = :ds, download_timestamp = :ts, download_skip_reason = :reason",
        ExpressionAttributeValues={
            ":ds": "DOWNLOAD_SKIPPED",
            ":ts": now,
            ":reason": skip_reason,
        },
    )
```

### Update `_write_pending()` to Set download_status

```python
def _write_pending(table, pk: str, sk: str, file_path: str, s3_key: str = "") -> None:
    record = build_default_record(pk, sk, file_path, s3_key=s3_key)
    record["id"] = str(uuid.uuid4())
    record["download_status"] = "QUEUED"  # ← NEW
    record["download_retry_count"] = 0     # ← NEW
    table.put_item(Item=record)
```

### Migration for Existing Records (batch.py)

```python
def _migrate_download_status(table) -> None:
    """Add download_status to old records. Safe to run multiple times."""
    scan_kwargs = dict(
        FilterExpression=Attr("download_status").not_exists(),
        ProjectionExpression="PK, SK, status",
    )
    migrated = 0
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            # Set based on current status
            status = item.get("status", "PENDING")
            if status == "COMPLETED":
                ds = "DOWNLOADED"  # was already processed
            elif status == "ERROR":
                ds = "DOWNLOAD_FAILED"  # download or processing failed
            else:
                ds = "QUEUED"  # default for PENDING or unknown
            
            table.update_item(
                Key={"PK": item["PK"], "SK": item["SK"]},
                UpdateExpression="SET download_status = :ds, download_retry_count = :zero",
                ExpressionAttributeValues={":ds": ds, ":zero": 0},
            )
            migrated += 1
        
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    
    log.info(f"Migration: added download_status to {migrated} records")
```

---

## New Configuration (core/config.py)

```python
S3_DOWNLOAD_BATCH_SIZE = int(os.environ.get("S3_DOWNLOAD_BATCH_SIZE", "200"))  # 0 = unlimited
S3_STAGING_DIR = os.environ.get("S3_STAGING_DIR", "/tmp/ahfl_staging")
```

---

## New Flow: Phase 1 (Bulk Download) + Phase 2 (Process)

```
run_batch_s3_v2(prefix, ...)
│
├── Extract month from prefix → "092021"
├── Get month table: ahfl_processed_data_092021
│
├── PHASE 1: BULK DOWNLOAD to persistent staging dir
│   │   staging_dir = /tmp/ahfl_staging/092021/  ← NOT auto-deleted
│   │
│   ├── _list_s3_keys(RAW_BUCKET, prefix)  → all keys for this month
│   ├── Filter out already COMPLETED + DOWNLOADED (from DB skip_paths)
│   ├── Apply batch_size cap → take first N remaining
│   └── For each key in batch:
│       ├── head_object size check
│       │   └── too large → write DOWNLOAD_SKIPPED + reason to DB, skip
│       ├── s3.download_file → staging_dir/app_number/attach_id/filename
│       ├── [OK]   → write DOWNLOADED to DB
│       └── [FAIL] → write DOWNLOAD_FAILED + error to DB, continue (don't abort batch)
│
└── PHASE 2: PROCESS all DOWNLOADED files in staging_dir
    └── For each local file with download_status=DOWNLOADED:
        ├── PENDING → PROCESSING (existing flow)
        ├── _process_pdf / _process_image
        ├── s3.upload_file → MASKED_BUCKET
        ├── COMPLETED → delete local staging file (reclaim disk)
        └── ERROR → keep local file for inspection
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Use DB for download tracking** | Crash-safe. If process dies at file 150/300, resuming restarts from 151 (not 0). Audit trail persists. |
| **Local variable not used** | Lost after process exit. No cross-run resumability. |
| **Separate `download_status` from `status`** | Clean separation. Download phase ≠ processing phase. |
| **Staging dir persistent, not ephemeral** | Phase 1 downloads all, Phase 2 processes all. Temp dir would auto-delete after Phase 1. |
| **Batch size = 200 (configurable, 0=unlimited)** | Operational control. Can process all 1000 files in run if set to 0, or chunk into runs of 200. |
| **>200 files per month handled via skip_paths** | If month has 1000 files and batch=200: Run 1 processes 200 (recorded in DB as COMPLETED), Run 2 picks up next 200 (via skip_paths). No re-download. |

---

## Summary of Changes

| Component | Change |
|-----------|--------|
| `core/config.py` | Add `S3_DOWNLOAD_BATCH_SIZE`, `S3_STAGING_DIR` |
| `core/db/database.py` | Add `download_status`, `download_timestamp`, `download_error`, `download_skip_reason`, `download_retry_count`, `local_staging_path` to schema |
| `batch.py` | Add `_update_download_queued()`, `_update_download_successful()`, `_update_download_failed()`, `_update_download_skipped()`, `_migrate_download_status()` |
| `batch.py` | Modify `_write_pending()` to set `download_status=QUEUED` |
| `batch.py` `run_batch_s3()` | Phase 1: bulk download to persistent staging with DB tracking; Phase 2: process from staging |
| CLI args | Add `--batch-size`, `--staging-dir` |

---

## Next Step

Ready to implement when you approve.
