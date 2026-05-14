#!/bin/bash

# NOTE: Enforce strict error handling so failed remote runs do not sync partial artifacts.
set -euo pipefail

# NOTE: Keep server connection config in one place for easier host/path updates.
REMOTE_HOST="habilelabsgpu"
REMOTE_ROOT="/srv/ahfl_working_gpu_new/ahfl-gpuvm"
REMOTE_VENV="${REMOTE_ROOT}/.venv_py310_paddle330_ocr340"
REMOTE_MODEL_DIR="${REMOTE_ROOT}/services/masking-engine/models"
REMOTE_ARTIFACT_ROOT="${REMOTE_ROOT}/debug_remote_artifacts"
LOCAL_ARTIFACT_ROOT="/Users/tusharjain/projects/AHFL/AHFL-GPU/ahfl-working-Gpu/habilelabsgpu-artifacts-output"

# Accept image path from argument or interactive prompt (for batch vs manual runs)
if [ $# -ge 1 ]; then
  IMG="$1"
else
  read -r -p "Enter image path: " IMG
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

# Preserve file extension (supports .pdf, .jpg, .png, .jpeg, etc.)
FILENAME=$(basename "$IMG")
EXTENSION="${FILENAME##*.}"
TEST_INPUT="/tmp/test_input.${EXTENSION}"

# NOTE: Upload one test file to a predictable remote temp path.
echo "Uploading: $IMG -> ${REMOTE_HOST}:${TEST_INPUT}"
scp "$IMG" "${REMOTE_HOST}:${TEST_INPUT}"

# NOTE: Run per-step visualizer so output structure matches old script behavior.
ssh "${REMOTE_HOST}" "
cd ${REMOTE_ROOT} && \
git pull origin cpu-testing && \
source ${REMOTE_VENV}/bin/activate && \
export PYTHONPATH=${REMOTE_ROOT} && \
export MODEL_MAIN=${REMOTE_MODEL_DIR}/main.pt && \
export MODEL_BEST=${REMOTE_MODEL_DIR}/best.pt && \
export MODEL_FRONT_BACK=${REMOTE_MODEL_DIR}/front_back_detect.pt && \
export MODEL_YOLO_N=${REMOTE_MODEL_DIR}/yolov8n.pt && \
python3 ${REMOTE_ROOT}/pipeline-visualizer-per-step.py \
  --input ${TEST_INPUT} \
  --out ${REMOTE_ARTIFACT_ROOT}
" 2>&1 | tee /tmp/habilelabsgpu_pipeline_run.log

# NOTE: With pipefail enabled, any remote python failure aborts script before rsync.
RUNFOLDER=$(ssh "${REMOTE_HOST}" "ls -td ${REMOTE_ARTIFACT_ROOT}/image-* | head -1")

# NOTE: Store artifacts under the new requested local folder name.
mkdir -p "${LOCAL_ARTIFACT_ROOT}"

rsync -avz \
  "${REMOTE_HOST}:${RUNFOLDER}/" \
  "${LOCAL_ARTIFACT_ROOT}/$(basename "$RUNFOLDER")/"

echo "✓ Results saved to: ${LOCAL_ARTIFACT_ROOT}/$(basename "$RUNFOLDER")/"
