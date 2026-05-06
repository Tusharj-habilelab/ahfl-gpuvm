# Migrated from: main.py + wsgi.py (AHFL-Masking 1.0) — Flask → FastAPI
# Role: Public-facing API gateway. Handles auth, validation, and delegates
#        all processing to the masking-engine service via HTTP.
#        wsgi.py is dropped — FastAPI uses Uvicorn directly.
"""
main.py — API Gateway FastAPI Service (AHFL-Masking 1.1)

Endpoints:
  POST /aadhaar-masking       — Upload file, authenticate, proxy to masking-engine
  GET  /masked/<filename>     — Serve masked output file for download
  GET  /                      — Health check

Replaces: main.py + wsgi.py (1.0 Flask application)
"""

import os
import hmac
import logging
import mimetypes
from pathlib import Path

import httpx
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────

app = FastAPI(
    title="AHFL Masking API Gateway",
    description="Authentication + routing gateway for the Aadhaar masking platform",
    version="1.1.0"
)

_allowed_origins = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["apiKey", "Content-Type"],
)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_FOLDER", "./output/masked"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MASKING_ENGINE_URL = os.environ.get("MASKING_ENGINE_URL", "http://masking-engine:8001")
AUTHORIZED_KEYS_PATH = os.environ.get("AUTHORIZED_KEYS_PATH", "config/authorized-keys.txt")
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", 15 * 1024 * 1024))


# ──────────────────────────────────────────────
# Auth helpers
# ──────────────────────────────────────────────

def _load_api_keys() -> set:
    """Load valid API keys from the authorized-keys file."""
    try:
        with open(AUTHORIZED_KEYS_PATH, "r") as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        log.warning(f"authorized-keys.txt not found at {AUTHORIZED_KEYS_PATH} — all requests will be rejected")
        return set()


def _validate_api_key(api_key: str) -> None:
    """Raise HTTPException if the API key is invalid."""
    if not api_key:
        log.warning("Auth rejected: missing API key")
        raise HTTPException(status_code=401, detail="API Key is missing.")
    keys = _load_api_keys()
    if not any(hmac.compare_digest(api_key, k) for k in keys):
        log.warning("Auth rejected: invalid API key")
        raise HTTPException(status_code=403, detail="Invalid API Key.")


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get("/")
async def health():
    return JSONResponse({"message": "AHFL Masking Gateway is up and running", "version": "1.1.0"})


@app.post("/aadhaar-masking")
async def create_upload_file(
    file: UploadFile = File(...),
    apiKey: str = Header(None),
):
    """
    Upload a file for Aadhaar masking.

    - Authenticates the API key from the `apiKey` header.
    - Validates file type (PDF, JPG, JPEG, PNG) and size (≤ 10 MB).
    - Forwards the file to the masking-engine service.
    - Returns the masking report and a download URL.
    """
    _validate_api_key(apiKey)

    allowed_ext = {"pdf", "jpg", "jpeg", "png"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed_ext:
        log.warning(f"File rejected: unsupported type '.{ext}' filename={file.filename}")
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '.{ext}'. Allowed: {allowed_ext}"
        )

    # Forward to masking-engine
    file_bytes = await file.read(MAX_FILE_SIZE + 1)
    if len(file_bytes) > MAX_FILE_SIZE:
        log.warning(f"File rejected: size {len(file_bytes)} > {MAX_FILE_SIZE} filename={file.filename}")
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_FILE_SIZE // (1024*1024)} MB limit.")

    log.info(f"Forwarding to masking-engine: filename={file.filename} size={len(file_bytes)}")
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            response = await client.post(
                f"{MASKING_ENGINE_URL}/mask",
                files={"file": (file.filename, file_bytes, file.content_type)},
            )
        except httpx.ConnectError:
            log.error(f"Masking engine unavailable: {MASKING_ENGINE_URL}")
            raise HTTPException(status_code=503, detail="Masking engine unavailable.")

    engine_data = response.json()

    if response.status_code != 200:
        log.error(f"Engine error {response.status_code}: {engine_data.get('detail', '')} filename={file.filename}")
        raise HTTPException(status_code=response.status_code, detail=engine_data.get("detail", "Engine error"))

    log.info(f"Success: filename={file.filename} pages={engine_data.get('total_pages')} masked={engine_data.get('total_pages_masked')}")

    host_url = os.environ.get("HOST", "http://localhost:8000")
    file_name = engine_data.get("fileName", "")
    download_url = f"{host_url}/masked/{file_name}"

    return JSONResponse({
        "status": 200,
        "statusMessage": "Success",
        "message": "File processed successfully.",
        "fileName": file_name,
        "downloadUrl": download_url,
        "total_pages": engine_data.get("total_pages"),
        "total_pages_masked": engine_data.get("total_pages_masked"),
        "logging_data": engine_data.get("page_reports"),
    })


@app.get("/masked/{filename:path}")
async def serve_masked_file(filename: str):
    """Serve a masked output file for download."""
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    file_path = OUTPUT_DIR / filename
    if not file_path.resolve().is_relative_to(OUTPUT_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(str(file_path), media_type=media_type or "application/octet-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0",
                port=int(os.environ.get("API_GATEWAY_PORT", 8000)),
                reload=False)
