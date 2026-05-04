# AHFL-Masking 1.1

Microservices re-architecture of the AHFL Aadhaar masking platform.
- **EasyOCR → PaddleOCR** migration complete
- **Flask → FastAPI** for all HTTP services
- **3 services** replacing the monolith: `api-gateway`, `masking-engine`, `batch-processor`
- **`core/`** shared library: zero code duplication between services

## Project Structure

```
AHFL-Masking 1.1/
├── core/                      # Shared library (single source of truth)
│   ├── masking.py             # ← paddleocr_integration/masking_functions.py
│   ├── ocr_adapter.py         # ← paddleocr_integration/paddle_ocr_adapter.py
│   ├── database.py            # ← utils/dbinit.py
│   ├── classifiers.py         # ← detect_aadhaar_side.py
│   └── utils/counts.py        # ← utils/count_pages_in_folder.py
├── services/
│   ├── api-gateway/           # ← main.py + wsgi.py (Flask → FastAPI)
│   ├── masking-engine/        # ← process_image.py (EasyOCR → PaddleOCR)
│   └── batch-processor/       # ← bulk.py + bulk-script/bulk1.py + bulk2.py
├── scripts/
│   ├── operational/           # ← server/scripts/
│   └── reporting/             # ← server/report/
├── research/
│   └── colab/                 # ← Colab-GPU/
├── docker-compose.yml
└── .env.example
```

## Quick Start

```bash
# 1. Copy and fill in env values
cp .env.example .env

# 2. Place model files in the models volume path or mount:
#    main.pt, best.pt, front_back_detect.pt, yolov8n.pt

# 3. Start API gateway + masking engine
docker compose up --build

# 4. Run batch processing (separate profile)
docker compose --profile batch run batch-processor \
  --source /path/to/source \
  --dest /path/to/output
```

## API

| Endpoint | Method | Description |
|---|---|---|
| `/aadhaar-masking` | POST | Upload file for masking (requires `apiKey` header) |
| `/masked/<filename>` | GET | Download masked file |
| `/` | GET | Gateway health check |
| `http://masking-engine:8001/health` | GET | Engine health check |
| `http://masking-engine:8001/mask` | POST | Direct engine call (internal) |

## Migration from 1.0

| 1.0 File | 1.1 Location | Notes |
|---|---|---|
| `main.py` | `services/api-gateway/main.py` | Flask → FastAPI |
| `wsgi.py` | ❌ Dropped | Uvicorn replaces WSGI |
| `process_image.py` | `services/masking-engine/engine.py` | EasyOCR → PaddleOCR |
| `bulk.py`, `bulk1.py`, `bulk2.py` | `services/batch-processor/batch.py` | Consolidated |
| `detect_aadhaar_side.py` | `core/classifiers.py` | Shared |
| `utils/dbinit.py` | `core/database.py` | Raises exceptions |
| `paddleocr_integration/masking_functions.py` | `core/masking.py` | Promoted to core |
| `paddleocr_integration/paddle_ocr_adapter.py` | `core/ocr_adapter.py` | Promoted to core |
