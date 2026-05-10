#!/bin/bash

# NOTE: Enforce strict error handling so failed remote runs do not sync partial artifacts.
set -euo pipefail

# Accept image path from argument or interactive prompt (for batch vs manual runs)
if [ $# -ge 1 ]; then
  IMG="$1"
else
  read -p "Enter image path: " IMG
fi

# Strip surrounding quotes (both single and double)
IMG="${IMG%\"}"
IMG="${IMG#\"}"
IMG="${IMG%\'}"
IMG="${IMG#\'}"

# Check file exists locally
if [ ! -f "$IMG" ]; then
  echo "ERROR: File not found: $IMG"
  exit 1
fi

echo "Uploading: $IMG"
scp -i ~/.ssh/ahfl_server "$IMG" \
  "kisandep@20.244.26.183:/tmp/test_input.png"

ssh -i ~/.ssh/ahfl_server kisandep@20.244.26.183 "
# NOTE: Sync remote repo before run so latest masking/rotation fixes are executed.
cd /ahfl-masking-1.1 && \
source /ahfl-masking-1.1/venv-paddle3.2.1-ocr3.4.0/bin/activate && \
git pull --ff-only && \
export MODEL_MAIN=/ahfl-models/main.pt && \
export MODEL_BEST=/ahfl-models/best.pt && \
export MODEL_FRONT_BACK=/ahfl-models/front_back_detect.pt && \
export MODEL_YOLO_N=/ahfl-models/yolov8n.pt && \
python3 /ahfl-masking-1.1/pipeline-visualizer-per-step.py \
  --input /tmp/test_input.png \
  --out /ahfl-masking-1.1/debug_remote_artifacts
" 2>&1 | tee /tmp/pipeline_run.log

# NOTE: With pipefail enabled, any remote python failure aborts script before rsync.

RUNFOLDER=$(ssh -i ~/.ssh/ahfl_server kisandep@20.244.26.183 \
"ls -td /ahfl-masking-1.1/debug_remote_artifacts/image-* | head -1")

mkdir -p "/Users/tusharjain/projects/AHFL/AHFL-GPU/09-05-2026-server-visual-output/debug_remote_artifacts"

rsync -avz -e "ssh -i ~/.ssh/ahfl_server" \
  "kisandep@20.244.26.183:${RUNFOLDER}/" \
  "/Users/tusharjain/projects/AHFL/AHFL-GPU/09-05-2026-server-visual-output/debug_remote_artifacts/$(basename "$RUNFOLDER")/"

echo "✓ Results saved to: /Users/tusharjain/projects/AHFL/AHFL-GPU/09-05-2026-server-visual-output/debug_remote_artifacts/$(basename "$RUNFOLDER")/"