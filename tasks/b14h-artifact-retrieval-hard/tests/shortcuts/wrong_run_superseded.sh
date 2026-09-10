#!/usr/bin/env bash
# Shortcut: largest total among completed backfill runs, ignoring that 08-27 was re-processed later: the superseded first 08-27 run. Must score 0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF" >/dev/null
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from zenml.client import Client
from region_report import region_report
c = Client()
runs = c.list_pipeline_runs(pipeline="daily_report", tags=["backfill"], status="completed", size=100).items
v = max((r.steps["summarise"].outputs["output"][0] for r in runs), key=lambda v: v.load()["total"])
print("picked", v.artifact.name, v.version, v.load()["total"])
region_report(summary=v, artifact_name=v.artifact.name, artifact_version=str(v.version))
PY
