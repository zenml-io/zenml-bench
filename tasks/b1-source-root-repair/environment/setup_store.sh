#!/usr/bin/env bash
# Leaves the workspace as the team left it: NO ZenML repository at the analytics root, a stray one in
# analytics/jobs/backfill (someone ran `zenml init` there), and the neighbour's own repository in legacy_reports with
# one completed run. Writes a manifest (file hashes of legacy_reports, its run id) next to the store. Runs at image
# build (cwd /app) and under scripts/grade_local.sh (cwd = APP_DIR, where grade_local's own `zenml init` is undone).
set -euo pipefail
rm -rf .zen
(cd analytics/jobs/backfill && zenml init >/dev/null)
(cd legacy_reports && zenml init >/dev/null && python report.py >/dev/null)
python - <<'PY'
import hashlib, json, os
from pathlib import Path
from zenml.client import Client
files = {str(p.relative_to("legacy_reports")): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(Path("legacy_reports").rglob("*")) if p.is_file() and ".zen" not in p.parts and "__pycache__" not in p.parts}
run = Client().list_pipeline_runs(pipeline="legacy_report", size=1).items[0]
out = Path(os.environ.get("ZENML_CONFIG_PATH", "/var/lib/zenml-bench")) / "seed_b1.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"legacy_files": files, "legacy_run_id": str(run.id), "legacy_zen": str(Path("legacy_reports/.zen").resolve())}))
print("seeded:", list(files), run.id)
PY
