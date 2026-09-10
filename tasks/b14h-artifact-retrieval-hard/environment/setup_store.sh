#!/usr/bin/env bash
# Produces the pipeline's real run history by running it (never by writing store rows): finance's hand-run
# backfill of late August (tagged `backfill` after the fact), in which three days were processed a second time
# because finance sent corrected exports, then the week of cron runs. Runs at image build (cwd /app/daily_report,
# after `zenml init`; backfill exports in /opt/backfill) and from scripts/grade_local.sh (exports next to this
# script). Writes a manifest of the seeded runs for the grader next to the store ($ZENML_CONFIG_PATH) or under
# /var/lib/zenml-bench.
set -uo pipefail
export ZENML_LOGGING_VERBOSITY=ERROR
HERE="$(cd "$(dirname "$0")" && pwd)"
BACKFILL="$HERE/backfill"; [ -d "$BACKFILL" ] || BACKFILL=/opt/backfill
run() { python run.py "$@" >/dev/null 2>&1 || true; }
# `load(date)` is cached on its code and its `date` parameter, not on the file, so a corrected export under the
# same name would be served from cache; the person re-processing expired the earlier step runs first.
expire() { python - <<'PY'
from datetime import datetime, timezone
from zenml.client import Client
c = Client()
for r in c.list_pipeline_runs(size=200).items:
    for s in r.steps.values(): c.update_step_run(s.id, cache_expires_at=datetime.now(timezone.utc))
PY
}
rm -rf reports && mkdir -p reports
for d in 2026-08-24 2026-08-25 2026-08-26 2026-08-27; do cp "$BACKFILL/$d.csv" "data/$d.csv"; done
run --date 2026-08-24                       # backfill, completed
run --date 2026-08-25                       # backfill, completed (16.2k)
mv reports reports.moving                   # the reports folder was being moved while this one ran...
run --date 2026-08-26                       # backfill: summary computed (17.2k, the largest of all), FileNotFoundError in `write_report`
mv reports.moving reports
run --date 2026-08-27                       # backfill, completed (16.7k): the largest completed total, later superseded
run --date 2026-08-28                       # backfill: no export for that day, FileNotFoundError in `load`
# finance sent corrected exports for three days; each was processed again
for d in 2026-08-25 2026-08-26 2026-08-27; do cp "$BACKFILL/$d.v2.csv" "data/$d.csv"; done
expire
run --date 2026-08-26                       # re-processed, completed (16.4k): the run finance means
mv reports reports.moving
run --date 2026-08-25                       # re-processed, FileNotFoundError in `write_report` (summary 17.0k): does not supersede 08-25
mv reports.moving reports
run --date 2026-08-27                       # re-processed, completed (15.0k): supersedes 08-27's first run
python - <<'PY'
from zenml.client import Client
from zenml.utils.tag_utils import add_tags
for r in Client().list_pipeline_runs(name="startswith:manual-2026-08-", size=50).items:
    add_tags(tags=["backfill"], run=r.id)
PY
run --date 2026-09-05 --trigger scheduled   # no export delivered: FileNotFoundError in `load`
run --date 2026-09-06 --trigger scheduled   # completed
run --date 2026-09-07 --trigger scheduled   # completed
run --date 2026-09-08 --trigger scheduled   # completed; larger total than any backfill day
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
