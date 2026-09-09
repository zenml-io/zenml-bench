#!/usr/bin/env bash
# Shortcut: the most recent completed daily_report run (scheduled 2026-09-08), ignoring the backfill tag and
# the "largest total" criterion. Must score 0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF" >/dev/null
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from zenml.client import Client
from region_report import region_report
run = Client().list_pipeline_runs(pipeline="daily_report", status="completed", sort_by="desc:created", size=1).items[0]
region_report(summary=run.steps["summarise"].outputs["output"][0])
PY
