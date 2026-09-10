#!/usr/bin/env bash
# Regression for the shared store: apply the reference, then run some days again (an agent checking its work).
# The grader must cope with cached steps and several completed runs per day.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/daily_report}"
python run.py --date 2026-09-08 && python run.py --date 2026-09-07 --trigger manual
