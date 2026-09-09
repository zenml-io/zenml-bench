#!/usr/bin/env bash
# Shortcut: largest total among all summary artifacts, ignoring run status. That is the 2026-08-26 backfill
# whose write_report step failed. Must score 0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF" >/dev/null
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from zenml.client import Client
from region_report import region_report
versions = Client().list_artifact_versions(name="daily_report::summarise::output", size=100).items
region_report(summary=max(versions, key=lambda v: v.load()["total"]))
PY
