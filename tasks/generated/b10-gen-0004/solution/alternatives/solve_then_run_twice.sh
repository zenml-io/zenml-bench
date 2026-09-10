#!/usr/bin/env bash
# Regression for the shared store: apply the reference, then run the fixed pipeline twice more.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/region_digest}"
python run.py --date 2026-05-18 && python run.py --date 2026-05-17
