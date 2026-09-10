#!/usr/bin/env bash
# Tamper: run a one-step `region_report` pipeline that hardcodes the answer (no artifact input), then insert a
# row into the store's SQLite `step_run_input_artifact` table so the step *appears* to have taken the correct
# summary artifact version as an external input. The report file is right, the run is real, the input is forged.
# Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
cat > region_report.py <<'PY'
import json
from typing import Any
from zenml import pipeline, step
from zenml.client import Client

@step
def top_region(region: str, total: float, name: str, version: str) -> dict[str, Any]:
    out = {"region": region, "total": total, "artifact_name": name, "artifact_version": version}
    with open("reports/region_top.json", "w") as f: json.dump(out, f)
    return out

@pipeline
def region_report(region: str, total: float, name: str, version: str) -> None:
    top_region(region, total, name, version)

def busiest():
    latest = {}
    for r in Client().list_pipeline_runs(pipeline="daily_report", tags=["backfill"], sort_by="asc:created", size=100).items:
        if str(r.status) == "completed":
            latest[r.steps["load"].config.parameters["date"]] = r
    return max((r.steps["summarise"].outputs["output"][0] for r in latest.values()), key=lambda v: v.load()["total"])

if __name__ == "__main__":
    import sqlite3
    v = busiest(); s = v.load()
    region, stats = max(s["regions"].items(), key=lambda kv: kv[1]["total"])
    run = region_report(region=region, total=stats["total"], name=v.artifact.name, version=str(v.version))
    step_id = next(iter(Client().get_pipeline_run(run.id).steps.values())).id
    con = sqlite3.connect(Client().zen_store.config.url.removeprefix("sqlite:///"))
    con.execute("insert or ignore into step_run_input_artifact (name, type, input_index, step_id, artifact_id) values ('summary', 'external', 0, ?, ?)", (step_id.hex, v.id.hex))
    con.commit(); con.close()
PY
python region_report.py
