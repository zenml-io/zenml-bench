#!/usr/bin/env bash
# Regression for the shared-store cache: apply the reference, then run the pipeline twice before grading.
# The grader's own run then has `train` CACHED and must still find churn_scorer as that run's output.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/churn_scoring}"
python run.py && python run.py
