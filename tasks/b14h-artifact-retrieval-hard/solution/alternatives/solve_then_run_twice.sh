#!/usr/bin/env bash
# Regression for the shared store: apply the reference, then run the new pipeline twice more. The later runs
# have the step CACHED; the recorded input must still be the historical artifact version.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/daily_report}"
python region_report.py && python region_report.py
