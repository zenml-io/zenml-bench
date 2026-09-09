#!/usr/bin/env bash
# Regression: apply the reference, run, temporarily change the scorer (a debug experiment), run again, revert, run.
# The latest `churn_scorer` version now comes from the debug run while the grader's run is served from cache
# with the earlier version. Found by an opus-5 trial; the grader must not require "latest == this run's output".
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/churn_scoring}"
python run.py
sed -i.bak 's/threshold=0.6/threshold=0.61/' run.py && python run.py
mv run.py.bak run.py && python run.py
