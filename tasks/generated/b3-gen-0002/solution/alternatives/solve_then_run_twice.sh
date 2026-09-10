#!/usr/bin/env bash
# Regression for the shared store: a correct fix must still pass after the agent has run the pipeline itself.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/overnight}"
python run.py && python run.py
