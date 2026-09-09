#!/usr/bin/env bash
# Alternative: look the artifact up by name and version number (`daily_report::summarise::output`, v<n>) rather
# than by id, pass it to the pipeline as an ExternalArtifact-free direct input.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF" >/dev/null
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from zenml.client import Client
from region_report import busiest_backfill_summary, region_report
v = busiest_backfill_summary()
same = Client().get_artifact_version(v.artifact.name, v.version)
assert same.id == v.id
region_report(summary=same)
PY
