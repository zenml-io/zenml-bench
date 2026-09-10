#!/usr/bin/env bash
# Produces the pipeline's real run history by running it (never by writing store rows). Generated for seed 1.
# Runs at image build (cwd /app/sales_summary, after `zenml init`) and from scripts/grade_local.sh. Writes a manifest of
# the seeded runs next to the store ($ZENML_CONFIG_PATH) or under /var/lib/zenml-bench (image).
set -uo pipefail
export ZENML_LOGGING_VERBOSITY=ERROR
run() { python run.py "$@" >/dev/null 2>&1 || true; }
rm -rf reports
run --date 2026-04-23 --trigger scheduled   # no data/2026-04-23.csv was delivered: FileNotFoundError in `load`
run --date 2026-04-24 --trigger scheduled   # reports/ did not exist yet: FileNotFoundError in `write_report`
mkdir -p reports                            # ...which someone fixed by hand the same day
run --date 2026-04-25 --trigger scheduled   # completed
run --date 2026-04-26 --trigger scheduled   # completed
run --date 2026-04-27 --trigger scheduled   # the real fault (paren_neg): ValueError in `parse`
run --date 2026-04-31                       # someone's typo, started by hand after the failure: FileNotFoundError in `load`
python - <<'PY'
import json, os
from pathlib import Path
from zenml.client import Client
out = Path(os.environ.get("ZENML_CONFIG_PATH") or "/var/lib/zenml-bench") / "seed_runs.json"
out.parent.mkdir(parents=True, exist_ok=True)
runs = [{"id": str(r.id), "name": r.name, "status": str(r.status), "tags": sorted(t.name for t in r.tags),
         "steps": {n: str(s.status) for n, s in r.steps.items()}}
        for r in Client().list_pipeline_runs(sort_by="asc:created", size=50).items]
out.write_text(json.dumps(runs, indent=1))
print(f"seeded {len(runs)} runs -> {out}")
for r in runs: print(f"  {r['name']:<40} {r['status']:<10} {r['steps']}")
PY
