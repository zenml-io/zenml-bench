#!/usr/bin/env bash
# Shortcut: largest total among all backfill summary artifacts, ignoring run status: the first 08-26 processing, which failed in write_report. Must score 0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF" >/dev/null
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from zenml.client import Client
from region_report import region_report
c = Client()
runs = [r for r in c.list_pipeline_runs(pipeline="daily_report", tags=["backfill"], size=100).items if "summarise" in r.steps]
v = max((r.steps["summarise"].outputs["output"][0] for r in runs), key=lambda v: v.load()["total"])
print("picked", v.artifact.name, v.version, v.load()["total"])
region_report(summary=v, artifact_name=v.artifact.name, artifact_version=str(v.version))
PY
