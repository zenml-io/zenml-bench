#!/usr/bin/env bash
# Regression: apply the reference, then temporarily change the summary (a debug experiment, rounding to 1 dp),
# run a day, revert, run it again. A completed run with the debug summary exists next to the correct ones.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/daily_report}"
sed -i.bak 's/round(float(g.mean()), 2)/round(float(g.mean()), 1)/' run.py && python run.py --date 2026-09-08
mv run.py.bak run.py && python run.py --date 2026-09-08
