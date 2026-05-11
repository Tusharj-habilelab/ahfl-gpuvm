# core/classifiers.py (inside _get_classifier)

model_path = os.environ.get("MODEL_FRONT_BACK", "models/front_back_detect.pt")
log.info(f"Loading front/back classifier from {model_path} on {_DEVICE}")
_model = YOLO(model_path).to(_DEVICE)
log.info("✓ front/back classifier loaded")

# services/masking-engine/engine.py (startup_event)

import core.classifiers as classifiers
logger.info("Preloading front/back and person models...")
classifiers._get_classifier()
classifiers._get_person_model()




logger.info("Preload complete")

I’ll inspect where YOLO model loading/logging happens, compare current behavior to expected logs, then give exact steps to copy `masked_output` from the server to your Mac.

Created 4 todos

I’m now scanning the codebase for YOLO model initialization and log statements to pinpoint why those lines disappeared.

Search complete: Find YOLO log code

Searched for files matching `**/batch_processor.py`, no matches

Searched for files matching `**/aadhaar_gate.py`, 1 match

Searched for regex `YOLO\(|ultralytics|model_path|loading model`, 200 results

Searched for files matching `**/config.py`, 1 match

Searched for files matching `**/yolo_runner.py`, 1 match

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/core/models/yolo_runner.py)

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/services/batch-processor/batch.py#1-1), lines 1 to 150

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/core/aadhaar_gate.py#1-1), lines 1 to 150

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/core/config.py#1-1), lines 1 to 100

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/needed%20action/missing-logging.md)

Searched for files matching `**/core/classifiers.py`, 1 match

Searched for files matching `**/services/masking-engine/engine.py`, 1 match

I found likely spots; next I’ll read the exact files to confirm the real code paths and give you a precise root cause, not guesses.

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/core/models/yolo_runner.py)

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/services/batch-processor/batch.py)

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/core/classifiers.py)

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/core/aadhaar_gate.py)

Searched for regex `preload_models\(` (`**/*.py`), 2 results

Read [](file:///Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/core/models/__init__.py)

I’ll check the latest aadhaar_gate.py change so I can tie your two runs (error run vs success run) to exact behavior.

Ran terminal command:  git --no-pager log -n 1 -- core/aadhaar_gate.py && echo '---' && git --no-pager show -n 1 -- core/aadhaar_gate.py | sed -n '1,220p'

Completed: *Inspect YOLO logging code paths* (1/4)

[Context: direct]

Yes. Your batch is working now. YOLO is running.

## Why YOLO model logs were not shown

The models are loaded lazily and inference logs prove they are active.You can see many Ultralytics lines like:

- `0: 448x640 1 aadhaar...`
- `0: 640x640 2 is_qrs...`

So YOLO did run.

What changed between failed run and working run:

- You first got: `"slow_conv2d_cpu" not implemented for 'Half'`
- Then you pulled commit `3bf8b05` (aadhaar_gate.py) and set `GPU_ENABLED=false`
- That commit changed half precision to:
  - `_USE_HALF = bool(GPU_ENABLED and torch.cuda.is_available())`
  - and uses `half=_USE_HALF` in YOLO calls
- That removed the FP16-on-CPU crash.

Why you may not see “YOLO Main: Initializing...” lines specifically:

- You may be running a different checkout/path on server than expected.
- Or preload block did not run in that execution path.
- Or logger output got mixed with model stdout.

## Logging status (exact check)

- `preload_models()` | `INFO` | `YOLO Main: Initializing...`, `YOLO Main: Ready`, `YOLO Best: Initializing...`, `YOLO Best: Ready`
- `get_yolo_main()` | `INFO` | `Loading YOLO main from ...`, `✓ YOLO main loaded on ...`
- `get_yolo_best()` | `INFO` | `Loading YOLO best from ...`, `✓ YOLO best loaded on ...`
- `_get_classifier()` | `❌ NO` | no model-load log currently
- `_get_person_model()` | `❌ NO` | no model-load log currently

If you want, I can add explicit INFO logs for `_get_classifier()` and `_get_person_model()` so model path/device always prints.

## What each model is doing

- `main.pt` (`MODEL_MAIN`)Primary detector on full/preprocessed image. Finds Aadhaar-related regions.
- `best.pt` (`MODEL_BEST`)Fine detector on Aadhaar crop (or fallback full image). Finds mask targets like number/QR variants.
- `front_back_detect.pt` (`MODEL_FRONT_BACK`)Secondary classifier to confirm Aadhaar front/back and reduce false positives.
- `yolov8n.pt` (`MODEL_YOLO_N`)
  Person detector used in PVC Aadhaar flow for photo-region masking.

## Copy `/ahfl-masking-1.1/masked_output` from server to your Mac

Run this on your **Mac terminal**:

```bash
mkdir -p "/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/masked_output_from_server"
rsync -avz --progress \
  kisandep@KisanDeploymentMachine:/ahfl-masking-1.1/masked_output/ \
  "/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/masked_output_from_server/"
```

If hostname does not resolve, replace `KisanDeploymentMachine` with server IP.

Quick verify on Mac:

```bash
find "/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/masked_output_from_server" -type f | wc -l
```

## Todo status

- [X] Inspect YOLO logging code paths
- [X] Identify why logs changed
- [X] Provide model meaning summary
- [X] Give server-to-Mac copy steps

— GitHub Copilot | 13:13:21 | 09-05-2026
