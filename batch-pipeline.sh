#!/bin/bash

# Batch runner: Loop through all images in a folder and run pipeline for each.
# Usage: bash batch-pipeline.sh /path/to/folder

set -euo pipefail

IMGFOLDER="${1:-.}"

if [ ! -d "$IMGFOLDER" ]; then
  echo "ERROR: Folder not found: $IMGFOLDER"
  exit 1
fi

echo "Scanning folder: $IMGFOLDER"
images=($(find "$IMGFOLDER" -maxdepth 1 \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) | sort))

if [ ${#images[@]} -eq 0 ]; then
  echo "ERROR: No images found in $IMGFOLDER"
  exit 1
fi

echo "Found ${#images[@]} images. Starting batch run..."
passed=0
failed=0

for img in "${images[@]}"; do
  echo ""
  echo "=========================================="
  echo "Processing: $(basename "$img")"
  echo "=========================================="
  
  if bash ./remote-pipeline.sh "$img"; then
    ((passed++))
    echo "✓ PASS: $(basename "$img")"
  else
    ((failed++))
    echo "✗ FAIL: $(basename "$img")"
  fi
done

echo ""
echo "=========================================="
echo "Batch complete: $passed passed, $failed failed"
echo "=========================================="

if [ $failed -gt 0 ]; then
  exit 1
fi
