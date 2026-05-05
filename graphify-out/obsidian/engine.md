---
id: services_masking_engine_engine_py
type: File
source: ./services/masking-engine/engine.py
community: 2
community_label: startup_event()
---

## Connections

- [[asyncio]] (imports)
- [[os]] (imports)
- [[uuid]] (imports)
- [[shutil]] (imports)
- [[tempfile]] (imports)
- [[gc]] (imports)
- [[logging]] (imports)
- [[signal]] (imports)
- [[pathlib_Path]] (imports)
- [[typing_Dict]] (imports)
- [[typing_Any]] (imports)
- [[fastapi_FastAPI]] (imports)
- [[fastapi_UploadFile]] (imports)
- [[fastapi_File]] (imports)
- [[fastapi_HTTPException]] (imports)
- [[fastapi_responses_FileResponse]] (imports)
- [[fastapi_responses_JSONResponse]] (imports)
- [[fastapi_middleware_cors_CORSMiddleware]] (imports)
- [[dotenv_load_dotenv]] (imports)
- [[ultralytics_YOLO]] (imports)
- [[torch]] (imports)
- [[core_get_yolo_main]] (imports)
- [[core_get_yolo_best]] (imports)
- [[core_config_GPU_MEMORY_FRACTION]] (imports)
- [[core_config_MAX_FILE_SIZE]] (imports)
- [[core_config_PDF_CHUNK_SIZE]] (imports)
- [[core_config_validate_required_env_vars]] (imports)
- [[core_config_GPU_ENABLED]] (imports)
- [[startup_event__]] (defines)
- [[_mask_single_image__]] (defines)
- [[_mask_pdf__]] (defines)
- [[health__]] (defines)
- [[health_detailed__]] (defines)
- [[mask_file__]] (defines)
- [[get_output_file__]] (defines)
- [[uvicorn]] (imports)
