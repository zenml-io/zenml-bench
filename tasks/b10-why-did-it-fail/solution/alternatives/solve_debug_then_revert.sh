#!/usr/bin/env bash
# Regression: apply the reference, run, temporarily change the summary (a debug experiment, rounding to 1 dp),
# run again, revert, run again. The latest summary artifact for 2026-09-09 comes from the *reverted* run, but a
# completed run with the debug summary also exists; the grader must accept a run whose summary is correct.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/daily_report}"
sed -i.bak 's/round(float(g.mean()), 2)/round(float(g.mean()), 1)/' run.py && python run.py --date 2026-09-09
mv run.py.bak run.py && python run.py --date 2026-09-09
