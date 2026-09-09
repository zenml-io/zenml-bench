#!/usr/bin/env bash
# Produces the pipeline's real run history by running it (never by writing store rows): finance's hand-run
# backfill of late August (tagged `backfill` after the fact, as the person who ran it did), then the week of
# cron runs. Runs at image build (cwd /app/daily_report, after `zenml init`; backfill exports in /opt/backfill)
# and from scripts/grade_local.sh (backfill exports next to this script). Writes a manifest of the seeded runs
# for the grader next to the store ($ZENML_CONFIG_PATH) or under /var/lib/zenml-bench.
set -uo pipefail
export ZENML_LOGGING_VERBOSITY=ERROR
HERE="$(cd "$(dirname "$0")" && pwd)"
run() { python run.py "$@" >/dev/null 2>&1 || true; }
cp "$HERE"/backfill/*.csv data/
rm -rf reports && mkdir -p reports
run --date 2026-08-24                       # backfill, completed
run --date 2026-08-25                       # backfill, completed
mv reports reports.moving                   # the reports folder was being moved while this one ran...
run --date 2026-08-26                       # backfill: summary computed, FileNotFoundError in `write_report` -> failed, largest total of all
mv reports.moving reports
run --date 2026-08-27                       # backfill, completed: the largest total among *completed* backfill runs
run --date 2026-08-28                       # backfill: no export for that day, FileNotFoundError in `load`
python - <<'PY'
from zenml.client import Client
from zenml.utils.tag_utils import add_tags
for r in Client().list_pipeline_runs(name="startswith:manual-2026-08-", size=50).items:
    add_tags(tags=["backfill"], run=r.id)
PY
run --date 2026-09-05 --trigger scheduled   # no export delivered: FileNotFoundError in `load`
run --date 2026-09-06 --trigger scheduled   # completed
run --date 2026-09-07 --trigger scheduled   # completed
run --date 2026-09-08 --trigger scheduled   # completed; larger total than any completed backfill day
run --date 2026-09-09 --trigger scheduled   # amounts with thousands separators -> ValueError in `parse`
run --date 2026-09-31                       # someone's typo: FileNotFoundError in `load`
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
for r in runs: print(f"  {r['name']:<40} {r['status']:<10} {r['tags']} {r['steps']}")
PY
