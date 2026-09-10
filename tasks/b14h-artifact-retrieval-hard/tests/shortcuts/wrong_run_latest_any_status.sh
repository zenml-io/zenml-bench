#!/usr/bin/env bash
# Shortcut: latest processing per day regardless of status, then largest total: the failed 08-25 re-processing. Must score 0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF" >/dev/null
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from zenml.client import Client
from region_report import region_report
c = Client()
latest = {}
for r in c.list_pipeline_runs(pipeline="daily_report", tags=["backfill"], sort_by="asc:created", size=100).items:
    if "summarise" in r.steps: latest[r.steps["load"].config.parameters["date"]] = r
v = max((r.steps["summarise"].outputs["output"][0] for r in latest.values()), key=lambda v: v.load()["total"])
print("picked", v.artifact.name, v.version, v.load()["total"])
region_report(summary=v, artifact_name=v.artifact.name, artifact_version=str(v.version))
PY
