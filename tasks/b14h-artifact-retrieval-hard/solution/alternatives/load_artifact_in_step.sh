#!/usr/bin/env bash
# Alternative: pass name and version as parameters and call `load_artifact` inside the step. ZenML records the
# loaded version as a `manual` input of the step, so the lineage is still there.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
cat > region_report.py <<'PY'
import json
from typing import Any

from zenml import load_artifact, pipeline, step
from zenml.client import Client


@step
def top_region(artifact_name: str, artifact_version: str) -> dict[str, Any]:
    summary = load_artifact(artifact_name, artifact_version)
    region, stats = max(summary["regions"].items(), key=lambda kv: kv[1]["total"])
    out = {"region": region, "total": stats["total"], "artifact_name": artifact_name, "artifact_version": artifact_version}
    with open("reports/region_top.json", "w") as f:
        json.dump(out, f)
    return out


@pipeline
def region_report(artifact_name: str, artifact_version: str) -> None:
    top_region(artifact_name, artifact_version)


if __name__ == "__main__":
    c = Client()
    latest = {}
    for r in c.list_pipeline_runs(pipeline="daily_report", tags=["backfill"], sort_by="asc:created", size=100).items:
        if str(r.status) == "completed":
            latest[r.steps["load"].config.parameters["date"]] = r
    best = max((r.steps["summarise"].outputs["output"][0] for r in latest.values()), key=lambda v: v.load()["total"])
    region_report(artifact_name=best.artifact.name, artifact_version=str(best.version))
PY
python region_report.py
