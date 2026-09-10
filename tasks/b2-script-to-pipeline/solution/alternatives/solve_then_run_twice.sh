#!/usr/bin/env bash
# Regression for the shared store: the conversion must still pass after the agent has run it on the visible data.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/credit_script}"
python train.py && python train.py
