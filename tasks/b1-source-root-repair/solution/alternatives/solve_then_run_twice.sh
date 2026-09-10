#!/usr/bin/env bash
# Regression for the shared store: the fix must still pass after the agent has run both entrypoints itself.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app}/analytics" && python pipelines/daily.py && (cd jobs/backfill && python run.py)
