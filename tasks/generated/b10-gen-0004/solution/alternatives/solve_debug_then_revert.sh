#!/usr/bin/env bash
# Regression: apply the reference, run, change the summary temporarily (a debug experiment), run, revert, run.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/region_digest}"
sed -i.bak 's/round(float(g.mean()), 2)/round(float(g.mean()), 1)/' run.py && python run.py --date 2026-05-18
mv run.py.bak run.py && python run.py --date 2026-05-18
