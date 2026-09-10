#!/usr/bin/env bash
# Alternative: pick the same version but fetch it by id; the name and version number cited in the report are
# read off the version object. The store records the same input either way.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF" >/dev/null
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from zenml.client import Client
from region_report import busiest_backfill_summary, region_report
name, version = busiest_backfill_summary()
v = Client().get_artifact_version(name, version)
by_id = Client().get_artifact_version(v.id)
region_report(summary=by_id, artifact_name=by_id.artifact.name, artifact_version=str(by_id.version))
PY
