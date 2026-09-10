#!/usr/bin/env bash
# Regression for the shared store: the fix must still pass after the agent has run the pipeline itself
# (the grader's first run then finds the loader already cached).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/sampling}"
python run.py && python run.py --n 37
