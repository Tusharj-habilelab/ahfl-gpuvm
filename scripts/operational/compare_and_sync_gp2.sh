#!/usr/bin/env bash
set -euo pipefail

OLD_ROOT="/Users/tusharjain/projects/ahfl-working-Gpu 2"
NEW_ROOT="/Users/tusharjain/projects/ahfl-working-Gpu"
PATCH_FILE=""
APPLY_SYNC=0
EXACT_SYNC=0

usage() {
  cat <<'EOF'
Compare and sync core/services between GPU2 and working project.

Usage:
  compare_and_sync_gp2.sh [options]

Options:
  --old-root PATH      Baseline project path (default: /Users/tusharjain/projects/ahfl-working-Gpu 2)
  --new-root PATH      Updated project path (default: /Users/tusharjain/projects/ahfl-working-Gpu)
  --patch-file FILE    Write a unified diff patch to FILE
  --apply              Copy changed/new files from new-root to old-root
  --exact              With --apply, also delete files missing in new-root
  -h, --help           Show this help message

Examples:
  # Compare only
  ./scripts/operational/compare_and_sync_gp2.sh

  # Compare + write patch
  ./scripts/operational/compare_and_sync_gp2.sh --patch-file /tmp/core-services.patch

  # Compare + apply updates
  ./scripts/operational/compare_and_sync_gp2.sh --apply
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --old-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --old-root" >&2; exit 1; }
      OLD_ROOT="$2"
      shift 2
      ;;
    --new-root)
      [[ $# -ge 2 ]] || { echo "Missing value for --new-root" >&2; exit 1; }
      NEW_ROOT="$2"
      shift 2
      ;;
    --patch-file)
      [[ $# -ge 2 ]] || { echo "Missing value for --patch-file" >&2; exit 1; }
      PATCH_FILE="$2"
      shift 2
      ;;
    --apply)
      APPLY_SYNC=1
      shift
      ;;
    --exact)
      EXACT_SYNC=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ $EXACT_SYNC -eq 1 && $APPLY_SYNC -eq 0 ]]; then
  echo "--exact can only be used with --apply" >&2
  exit 1
fi

for subdir in core services; do
  [[ -d "$OLD_ROOT/$subdir" ]] || { echo "Missing directory: $OLD_ROOT/$subdir" >&2; exit 1; }
  [[ -d "$NEW_ROOT/$subdir" ]] || { echo "Missing directory: $NEW_ROOT/$subdir" >&2; exit 1; }
done

compare_one() {
  local subdir="$1"
  echo "===== $subdir: changed files ====="
  diff -qr -x ".DS_Store" -x "__pycache__" -x "*.pyc" "$OLD_ROOT/$subdir" "$NEW_ROOT/$subdir" || true
  echo

  echo "===== $subdir: line stats ====="
  git --no-pager diff --no-index --numstat -- "$OLD_ROOT/$subdir" "$NEW_ROOT/$subdir" \
    | grep -Ev '\.DS_Store|/__pycache__/|\.pyc' || true
  echo
}

for subdir in core services; do
  compare_one "$subdir"
done

if [[ -n "$PATCH_FILE" ]]; then
  mkdir -p "$(dirname "$PATCH_FILE")"
  : > "$PATCH_FILE"
  has_diff=0

  for subdir in core services; do
    if diff -ruN -x ".DS_Store" -x "__pycache__" -x "*.pyc" "$OLD_ROOT/$subdir" "$NEW_ROOT/$subdir" >> "$PATCH_FILE"; then
      :
    else
      rc=$?
      if [[ $rc -eq 1 ]]; then
        has_diff=1
      else
        echo "Failed while generating patch for $subdir" >&2
        exit "$rc"
      fi
    fi
  done

  if [[ $has_diff -eq 0 ]]; then
    echo "# No differences found for core/services." > "$PATCH_FILE"
  fi

  echo "Unified diff saved to: $PATCH_FILE"
  echo
fi

if [[ $APPLY_SYNC -eq 1 ]]; then
  rsync_flags=(-av --itemize-changes --exclude=".DS_Store" --exclude="__pycache__/" --exclude="*.pyc")
  if [[ $EXACT_SYNC -eq 1 ]]; then
    rsync_flags+=(--delete)
  fi

  echo "===== syncing core ====="
  rsync "${rsync_flags[@]}" "$NEW_ROOT/core/" "$OLD_ROOT/core/"
  echo

  echo "===== syncing services ====="
  rsync "${rsync_flags[@]}" "$NEW_ROOT/services/" "$OLD_ROOT/services/"
  echo

  echo "Sync completed."
fi
