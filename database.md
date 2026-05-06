# Database Schema & Records

## Table Overview

**Name:** `ahfl_processed_data` (configurable via `TABLE_NAME` env var)
**Region:** `ap-south-1` (configurable via `AWS_REGION` env var)
**Auth:** EC2 IAM role (no credentials needed on GPU VM)

---

## Primary Keys

| Key | Type | Value | Purpose |
|-----|------|-------|---------|
| **PK** | String | `DOC#<file_path>` | Partition key — unique per file |
| **SK** | String | ISO timestamp | Sort key — record creation time |

---

## Global Secondary Index (GSI1)

Enables status-based queries + time sorting.

| Index Key | Type | Value | Purpose |
|-----------|------|-------|---------|
| **GSI1PK** | String | `STATUS#<status>` | Query by status (PENDING/PROCESSING/COMPLETED/ERROR) |
| **GSI1SK** | String | ISO timestamp | Sort results by time within status |

---

## All Fields Recorded

### Identification
| Field | Type | Value |
|-------|------|-------|
| `PK` | String | `DOC#<path>` |
| `SK` | String | ISO timestamp (e.g., 2026-05-04T10:30:00Z) |
| `file_path` | String | Local or S3 path |
| `s3_key` | String | S3 object key (S3 mode) |

### Processing Status
| Field | Type | Values | Meaning |
|-------|------|--------|---------|
| `status` | String | PENDING / PROCESSING / COMPLETED / ERROR | Current processing state |
| `retryAttempts` | Number | 0-N | Retry count on failure |
| `createdAt` | String | ISO timestamp | Record creation time |
| `updatedAt` | String | ISO timestamp | Last update time |

### Document Classification
| Field | Type | Values | Meaning |
|-------|------|--------|---------|
| `lane_chosen` | String | form / card / uncertain | Routing lane assigned |
| `card_detected` | Boolean | true/false | YOLO found Aadhaar card? |
| `aadhaar_verified` | Boolean | true/false | OCR confirmed Aadhaar text? |
| `pan_found` | Boolean | true/false | PAN card detected? |
| `skip_reason` | String | skip_keywords / pan_card / cersai_found / null | Why document was skipped (if skipped) |

### Orientation & Angle Correction
| Field | Type | Value |
|-------|------|-------|
| `orientation_hint_angle` | Number | (unused) |
| `final_winning_angle` | Number | 0, 90, 180, or 270 degrees |

### Masking Counts (Dual Schema)

**Flat fields** (backward compatibility):
```
is_aadhaar: number
is_number: number
is_number_masked: number
is_QR: number
is_QR_masked: number
is_XX: number
ocr_patterns_found: number
```

**Nested object** (new schema, authoritative):
```json
mask_counts: {
  "is_aadhaar": 0,
  "is_number": 0,
  "is_number_masked": 0,
  "is_qr": 0,
  "is_qr_masked": 0,
  "is_xx": 0,
  "ocr_patterns_found": 0
}
```

### PDF Metadata
| Field | Type | Value |
|-------|------|-------|
| `totalPages` | Number | Total pages in PDF |
| `scannedPages` | Number | Pages successfully processed |
| `maskedPages` | Number | Pages with masking applied |
| `pageReports` | Object | Per-page metadata (usually empty) |

### GSI Fields
| Field | Type | Value |
|-------|------|-------|
| `GSI1PK` | String | `STATUS#<status>` |
| `GSI1SK` | String | ISO timestamp |

---

## Record Lifecycle

```
Step 1: PRE-WRITE (file added to batch queue)
  status = PENDING
  retryAttempts = 0
  lane_chosen = unknown
  skip_reason = null
  createdAt = 2026-05-04T10:30:00Z
  ↓
Step 2: PROCESSING (batch-processor starts file)
  status = PROCESSING
  updatedAt = 2026-05-04T10:30:05Z
  ↓
Step 3a: SUCCESS (file masked successfully)
  status = COMPLETED
  lane_chosen = form|card|uncertain
  card_detected = true|false
  aadhaar_verified = true|false
  mask_counts = {...}
  final_winning_angle = 0|90|180|270
  updatedAt = 2026-05-04T10:30:45Z
  ↓
Step 3b: SKIP (file flagged for skip)
  status = COMPLETED
  skip_reason = skip_keywords|pan_card|cersai_found
  ↓
Step 3c: FAILURE (exception during processing)
  status = ERROR
  retryAttempts += 1
  updatedAt = 2026-05-04T10:30:50Z
```

---

## Query Patterns

### By File (Single Record Lookup)
```
PK = DOC#/path/to/file.pdf
SK = 2026-05-04T10:30:00Z
```
Returns: Single record with full metadata

### By Status (Batch Query)
```
GSI1PK = STATUS#COMPLETED
GSI1SK >= 2026-05-01T00:00:00Z
```
Returns: All completed files after date, sorted by time

### Skip Detection (Already Processed?)
```
GSI1PK = STATUS#COMPLETED
filter: file_path = /path/to/file.pdf
```
Returns: Empty → can process; Non-empty → already done

---

## Default Record Template

```python
{
  "PK": "DOC#/path/to/file.pdf",
  "SK": "2026-05-04T10:30:00Z",
  "file_path": "/path/to/file.pdf",
  "s3_key": "",
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
  "mask_counts": {
    "is_aadhaar": 0,
    "is_number": 0,
    "is_number_masked": 0,
    "is_qr": 0,
    "is_qr_masked": 0,
    "is_xx": 0,
    "ocr_patterns_found": 0
  },
  "lane_chosen": "unknown",
  "orientation_hint_angle": null,
  "final_winning_angle": null,
  "skip_reason": null,
  "card_detected": false,
  "aadhaar_verified": false,
  "pan_found": false,
  "pageReports": {},
  "GSI1PK": "STATUS#PENDING",
  "GSI1SK": "2026-05-04T10:30:00Z",
  "createdAt": "2026-05-04T10:30:00Z",
  "updatedAt": "2026-05-04T10:30:00Z"
}
```

---

## Backward Compatibility Notes

- **Flat fields** (`is_aadhaar`, `is_QR`, etc.) maintained for old queries/reports
- **Nested mask_counts** is the canonical source (authoritative)
- Both stay in sync during writes
- Queries can use either, but mask_counts is preferred for new code

---

Generated: 2026-05-04
Source: core/db/database.py:35-67
