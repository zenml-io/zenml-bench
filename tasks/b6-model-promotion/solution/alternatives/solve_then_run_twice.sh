#!/usr/bin/env bash
# Regression for the shared store: the fix must still pass after the agent has run inference several times.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/model_promotion}"
python inference.py && python inference.py --input data/batch.csv
