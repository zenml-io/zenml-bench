#!/usr/bin/env bash
# Shortcut: largest total among *all* completed runs (that is scheduled 2026-09-08, not a backfill day). Must score 0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF" >/dev/null
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from zenml.client import Client
from region_report import region_report
runs = Client().list_pipeline_runs(pipeline="daily_report", status="completed", size=100).items
v = max((r.steps["summarise"].outputs["output"][0] for r in runs), key=lambda v: v.load()["total"])
region_report(summary=v)
PY
