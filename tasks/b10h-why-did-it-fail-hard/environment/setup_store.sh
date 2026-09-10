#!/usr/bin/env bash
# Produces the pipeline's real run history by running it (never by writing store rows): the week the cron job
# has been live, with two data faults on different days, two failures no code change caused, and a manual
# distractor. The exports of failed days are then removed, as the on-call's quarantine step does, so at agent
# time the recorded step output and traceback are the only evidence of what those files contained.
# Runs at image build (cwd /app/daily_report, after `zenml init`; build-only exports in /opt/exports) and from
# scripts/grade_local.sh (exports next to this script). Writes a manifest of the seeded runs for the grader
# next to the store ($ZENML_CONFIG_PATH) or under /var/lib/zenml-bench.
set -uo pipefail
export ZENML_LOGGING_VERBOSITY=ERROR
HERE="$(cd "$(dirname "$0")" && pwd)"
EXPORTS="$HERE/exports"; [ -d "$EXPORTS" ] || EXPORTS=/opt/exports
run() { python run.py "$@" >/dev/null 2>&1 || true; }
rm -rf reports && mkdir -p reports
cp "$EXPORTS/2026-08-30.csv" data/
run --date 2026-08-30                       # someone re-ran an old export by hand: its timestamps are ISO ("T") -> ValueError in `parse`; not a scheduled run
rm data/2026-08-30.csv
run --date 2026-09-02 --trigger scheduled   # completed
cp "$EXPORTS/2026-09-03.csv" data/
run --date 2026-09-03 --trigger scheduled   # fault 2: region names "North" / "west " -> ValueError in `summarise`
rm data/2026-09-03.csv                      # ...the on-call quarantined the export
run --date 2026-09-04 --trigger scheduled   # completed
run --date 2026-09-05 --trigger scheduled   # no export delivered: FileNotFoundError in `load`
rm -rf reports
run --date 2026-09-06 --trigger scheduled   # reports/ had been removed in a clean-up: FileNotFoundError in `write_report`
mkdir -p reports                            # ...recreated by hand the same day
run --date 2026-09-07 --trigger scheduled   # completed
run --date 2026-09-08 --trigger scheduled   # completed
cp "$EXPORTS/2026-09-09.csv" data/
run --date 2026-09-09 --trigger scheduled   # fault 1, this morning: amounts "1,234.50" -> ValueError in `parse`
rm data/2026-09-09.csv                      # ...quarantined
run --date 2026-09-31                       # someone's typo, by hand, after the failure: FileNotFoundError in `load`
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
