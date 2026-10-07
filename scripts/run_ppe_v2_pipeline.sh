#!/usr/bin/env bash
# PPE v2: everything after the teachers are trained (see docs/DATA.md).
#   check teachers on held-out test splits -> pseudo-label missing classes (conf >= 0.5)
#   -> filter pseudo-labels (drop machinery; gear must sit on a detected person)
#   -> spot-check sheets -> build merged train/val + test sets -> train + evaluate v2
# Run from the repo root:  bash scripts/run_ppe_v2_pipeline.sh
set -euo pipefail
STEP="start"
trap 'echo "[$(date "+%F %T")] FAILED at step: $STEP (see runs/ppe_v2/*.log)" >&2' ERR
PY=.venv/Scripts/python.exe
LOG=runs/ppe_v2
mkdir -p "$LOG"
echo "[$(date '+%F %T')] check teachers"; STEP="check teachers"
$PY -u scripts/data_pseudolabel.py check > "$LOG/teacher_check.log" 2>&1
echo "[$(date '+%F %T')] pseudo-label"; STEP="pseudo-label"
$PY -u scripts/data_pseudolabel.py label --conf 0.5 > "$LOG/pseudolabel.log" 2>&1
echo "[$(date '+%F %T')] filter pseudo-labels (class policy + person consistency)"; STEP="filter pseudo-labels (class policy + person consistency)"
$PY -u scripts/data_pseudolabel.py filter > "$LOG/pseudo_filter.log" 2>&1
echo "[$(date '+%F %T')] build"; STEP="build"
$PY -u scripts/data_build.py > "$LOG/build.log" 2>&1
echo "[$(date '+%F %T')] review sheets"; STEP="review sheets"
for s in hardhat_xie gdut_hwd chvg rf100_construction_safety rf100_excavators kr_site_machinery; do
  $PY scripts/data_review.py --root merged --source "$s" --split train --pseudo-only -n 16 --tag pseudo >> "$LOG/review.log" 2>&1 || true
done
echo "[$(date '+%F %T')] train v2"; STEP="train v2"
$PY -u scripts/train_ppe_v2.py --epochs "${EPOCHS:-50}" --patience "${PATIENCE:-12}" --batch "${BATCH:-32}" \
  --workers "${WORKERS:-8}" --cache disk > "$LOG/train_v2.log" 2>&1
echo "[$(date '+%F %T')] done"
