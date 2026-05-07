# Missed logging — snapshot

Created: 2026-05-07
Source: session audit and code review (batch-processor, masking-engine, api-gateway, core modules)

Summary: items currently not being logged (or insufficiently logged) that should be added for observability, debugging, and audit.

## Core / configuration

- `core/config.py`
  - Log loaded environment values at startup (sanitized). Key vars: `PADDLE_MODEL_DIR`, `MODEL_MAIN`, `MODEL_BEST`, `GPU_ENABLED`, `TABLE_NAME`, `RAW_BUCKET`, `MASKED_BUCKET`.

## OCR / Paddle

- `core/ocr/paddle.py`
  - Log resolved `model_dir` used by PaddleOCR (explicit or default `~/.paddlex`).
  - Log model download start/complete and download errors. Include model name and target path.
  - Log cache path resolution (symlink detection: `/root/.paddlex` -> actual path).

## Masking engine

- `services/masking-engine/engine.py`
  - On startup: log list of models loaded (file paths), device selected (cuda id or cpu), GPU memory available, and model load durations.
  - Per-request: assign correlation id; log request start, payload size/type, processing start/end time, duration, and status code.
  - Log preprocessing decisions (e.g., orientation detection result, fallback paths).
  - Log exceptions with full stack and correlation id.

## API gateway

- `services/api-gateway/main.py`
  - Log incoming requests: route, masked apiKey (partial), client IP, timestamp.
  - Log proxied call to masking-engine: start/finish times, status code, latency, and errors.

## Batch processor

- `services/batch-processor/batch.py`
  - At run start: log total files discovered, counts per extension, and effective include/exclude filters.
  - Per-file: log processing start/finish, duration, output path, status (skipped/processed/error), and correlation id.
  - DB state transitions: log each transition (pending -> processing -> completed/error) with record id and timestamps.
  - `_get_skip_paths`: log when a full table scan is used (duration, item count). Prefer logging query type chosen.
  - S3 operations: log download/upload start/finish, bytes transferred, durations, and retry attempts.
  - PDF processing: log chunk boundaries, pages processed per chunk, and blank-page fallback events.
  - `to_skip_file()` decisions: log skip reasons per file (keyword match, already processed, unsupported ext).

## Model preload & warmup

- `preload_models()` or equivalent:
  - Log warmup start/complete per model and timings.
  - Detect and log duplicate warmup attempts (dead/duplicate code note).

## Error handling, tracing & metrics

- Structured error logs: include correlation id, module, function, and full stack trace.
- Add correlation id generation (UUID) for each external request and batch run; include in all related logs.
- Periodic metrics summary: processed count, success rate, avg latency, error counts. Export or log regularly.

## Health & startup

- `/health/detailed`: include logs for GPU driver version, CUDA version, GPU memory free, disk free space, and loaded model paths.
- Startup cleanup: log stale `PROCESSING` records removed on startup with count and ids.

## Security & audit

- Repo secrets detection: log if `.env` present in repo on startup (warn), but do not print secret values.
- Token/credential rotation events: log revocation and replacement events (audit only).

---

Next steps (short):
1. Implement structured logging (JSON) using `logging` or `structlog`.
2. Add correlation id propagation to API/gateway/batch flows.
3. Instrument key locations above and run end-to-end to collect examples.


