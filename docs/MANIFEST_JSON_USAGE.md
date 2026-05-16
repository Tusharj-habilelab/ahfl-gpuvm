# How manifest.json is Used in Batch Download Flow

## Overview

`manifest.json` is a **static snapshot** of all S3 keys for one batch-prefix. It's created once and reused across restarts to avoid re-listing S3 (which costs money).

---

## File Location

```
/var/tmp/ahfl_batch/<batch_prefix>/<run_id>/manifest.json
```

**Example:**
```
/var/tmp/ahfl_batch/092021_1/run_20260515_143000/manifest.json
```

---

## File Format

```json
{
  "batch_prefix": "092021_1",
  "generated_at": "2026-05-15T14:30:00Z",
  "count": 1234,
  "keys": [
    {
      "key": "092021_1/092021/1/Audit_documents/00460861/2297504/doc1.pdf",
      "size": 12345,
      "etag": "\"abc123def456\"",
      "last_modified": "2026-04-01T12:00:00Z"
    },
    {
      "key": "092021_1/092021/1/Audit_documents/00460861/2297505/doc2.pdf",
      "size": 23456,
      "etag": "\"xyz789uvw012\"",
      "last_modified": "2026-04-01T12:01:00Z"
    }
  ]
}
```

---

## When manifest.json is Created

### First Run (No manifest exists)

```
START batch.py --s3 --prefix "092021_1"
  │
  ├─ Check: /var/tmp/ahfl_batch/092021_1/run_20260515_143000/manifest.json exists?
  │         NO → proceed to create
  │
  ├─ Call S3 ListObjectsV2 for prefix "092021_1"
  │         Returns: 1234 keys with size, etag, last_modified
  │
  ├─ Write manifest.json with all 1234 keys
  │         (atomic write: temp file → rename)
  │
  └─ Continue with download phase
```

**Cost:** 1 S3 ListObjectsV2 call (charged)

---

## When manifest.json is Reused

### Restart After Crash (manifest exists)

```
RESTART batch.py --s3 --prefix "092021_1"
  │
  ├─ Check: /var/tmp/ahfl_batch/092021_1/run_20260515_143000/manifest.json exists?
  │         YES → load it (NO S3 call)
  │
  ├─ Load 1234 keys from manifest.json
  │
  ├─ Query DynamoDB for batch_prefix = "092021_1"
  │         Returns: keys already DOWNLOADED or COMPLETED
  │
  ├─ Compute pending list
  │         pending = manifest keys − DB completed keys
  │         Example: 1234 − 800 = 434 files still need download
  │
  ├─ Resume download for 434 pending files
  │         (skip the 800 already done)
  │
  └─ Continue
```

**Cost:** 0 S3 ListObjectsV2 calls (saved!)

---

## Download Phase Using manifest.json

### Step-by-Step Flow

```
FOR EACH key in manifest.json["keys"]:
  │
  ├─ 1. Check DB: is this key already DOWNLOADED or COMPLETED?
  │        YES → skip to next key (already done)
  │        NO  → proceed to download
  │
  ├─ 2. Check local spool: does file exist at /var/tmp/ahfl_batch/092021_1/<run_id>/downloads/<key>?
  │        YES → mark DOWNLOADED in buffer (no re-download)
  │        NO  → proceed to S3 download
  │
  ├─ 3. Download from S3
  │        s3.download_file(RAW_BUCKET, key, local_spool_path)
  │        Save to: /var/tmp/ahfl_batch/092021_1/<run_id>/downloads/092021_1/092021/1/Audit_documents/.../doc.pdf
  │
  ├─ 4. On success:
  │        Add to in-memory buffer:
  │        {
  │          "pk": "092021_1",
  │          "sk": key,
  │          "status": "DOWNLOADED",
  │          "size": 12345,
  │          "etag": "\"abc123\"",
  │          "timestamp": "2026-05-15T14:35:00Z"
  │        }
  │
  ├─ 5. On failure:
  │        Add to in-memory buffer:
  │        {
  │          "pk": "092021_1",
  │          "sk": key,
  │          "status": "ERROR_DOWNLOAD",
  │          "reason_message": "Connection timeout",
  │          "attempt_count": 1
  │        }
  │        Flush buffer to DB immediately (failures go right away)
  │
  ├─ 6. Buffer size >= 25?
  │        YES → flush buffer to DynamoDB, clear buffer
  │        NO  → continue to next key
  │
  └─ END of all keys
       Flush remaining buffer to DB (final flush)
```

---

## Key Benefits of manifest.json

| Benefit | How It Works |
|---------|-------------|
| **Cost Savings** | S3 ListObjectsV2 called only once per batch-prefix, not per restart |
| **Fast Restart** | Load manifest from disk (instant) instead of re-listing S3 (slow + expensive) |
| **Crash Safety** | manifest.json + DB query = deterministic resume state |
| **Deduplication** | Compare manifest keys with DB completed keys to skip already-done files |
| **Audit Trail** | manifest.json records size/etag/last_modified for each file |

---

## Example Scenario: Crash and Resume

### Run 1: First Attempt (Crash at file 500 of 1234)

```
Time: 14:30:00 - Create manifest.json (1234 keys)
Time: 14:30:05 - Start downloading
Time: 14:35:00 - Downloaded 500 files successfully
Time: 14:35:15 - Network error, process crashes
Time: 14:35:15 - 500 files in DB with status=DOWNLOADED
Time: 14:35:15 - 734 files still pending
```

**Files on disk:**
```
/var/tmp/ahfl_batch/092021_1/run_20260515_143000/
├── manifest.json (1234 keys)
├── downloads/
│   ├── 092021_1/092021/1/Audit_documents/.../doc1.pdf (500 files)
│   └── ...
└── masked/
    └── (empty, processing not started yet)
```

### Run 2: Restart (Resume)

```
Time: 14:40:00 - Restart batch.py --s3 --prefix "092021_1"
Time: 14:40:01 - Load manifest.json (instant, no S3 call)
Time: 14:40:02 - Query DB for batch_prefix="092021_1"
                  Returns: 500 keys with status=DOWNLOADED
Time: 14:40:03 - Compute pending = 1234 - 500 = 734 files
Time: 14:40:04 - Check local spool: 500 files exist
                  Mark them as DOWNLOADED (no re-download)
Time: 14:40:05 - Resume download for remaining 734 files
Time: 14:50:00 - All 1234 files downloaded
```

**Cost Saved:**
- Run 1: 1 ListObjectsV2 call
- Run 2: 0 ListObjectsV2 calls (manifest reused)
- **Total: 1 call instead of 2** ✓

---

## Manifest Lifecycle

### Creation
```python
# First run only
manifest = {
    "batch_prefix": "092021_1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "count": len(keys),
    "keys": [
        {
            "key": obj["Key"],
            "size": obj["Size"],
            "etag": obj["ETag"],
            "last_modified": obj["LastModified"].isoformat()
        }
        for obj in s3_response["Contents"]
    ]
}
# Write atomically: temp file → rename
```

### Loading
```python
# Restart or resume
with open(manifest_path, "r") as f:
    manifest = json.load(f)
    
# Validate
assert manifest["batch_prefix"] == "092021_1"
assert manifest["count"] == len(manifest["keys"])

# Use
pending_keys = [k["key"] for k in manifest["keys"]]
```

### Cleanup
```python
# After batch complete (optional)
# Keep manifest for audit trail
# Or delete if storage is tight
os.remove(manifest_path)
```

---

## Comparison: With vs Without manifest.json

### Without manifest.json (Current Code)

```
Run 1: ListObjectsV2 → download 500 files → crash
Run 2: ListObjectsV2 again → download 500 files again → crash
Run 3: ListObjectsV2 again → download 500 files again → success

Cost: 3 ListObjectsV2 calls + 1500 file downloads
```

### With manifest.json (Proposed)

```
Run 1: ListObjectsV2 → save manifest.json → download 500 files → crash
Run 2: Load manifest.json → download 734 files → crash
Run 3: Load manifest.json → download 734 files → success

Cost: 1 ListObjectsV2 call + 1234 file downloads
```

**Savings: 2 ListObjectsV2 calls per batch-prefix** ✓

---

## Implementation Checklist

- [ ] Create manifest.json on first run
- [ ] Load manifest.json on restart
- [ ] Validate manifest format (batch_prefix, count, keys)
- [ ] Use manifest keys instead of re-listing S3
- [ ] Query DB to find already-downloaded keys
- [ ] Skip already-downloaded files (check local spool)
- [ ] Buffer download status rows (25-100 per flush)
- [ ] Flush buffer to DB on size or at end
- [ ] Immediate flush on download errors
- [ ] Log manifest creation and load events

---

## Questions?

**Q: What if manifest.json is corrupted?**  
A: Validate on load. If invalid, delete and re-create (one extra ListObjectsV2 call).

**Q: What if S3 keys change between runs?**  
A: manifest.json is per-run. New run = new manifest. Old manifest ignored.

**Q: Can multiple processes share manifest.json?**  
A: No. Use lock file (`manifest.lock`) or unique run_id per process.

**Q: How long to keep manifest.json?**  
A: Keep until batch complete. Delete after final flush to DB (optional).
