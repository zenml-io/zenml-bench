#!/usr/bin/env bash
# Alternative: pass the artifact version id as a parameter and call `load_artifact` inside the step. ZenML
# records the loaded version as a `manual` input of the step, so the lineage is still there.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
cat > region_report.py <<'PY'
import json
from typing import Any

from zenml import load_artifact, pipeline, step
from zenml.client import Client


@step
def top_region(artifact_version_id: str) -> dict[str, Any]:
    summary = load_artifact(artifact_version_id)
    region, stats = max(summary["regions"].items(), key=lambda kv: kv[1]["total"])
    out = {"region": region, "total": stats["total"]}
    with open("reports/region_top.json", "w") as f:
        json.dump(out, f)
    return out


@pipeline
def region_report(artifact_version_id: str) -> None:
    top_region(artifact_version_id)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        region_report(artifact_version_id=sys.argv[1]); raise SystemExit(0)
    c = Client()
    best = None
    for r in c.list_pipeline_runs(pipeline="daily_report", tags=["backfill"], size=100).items:
        if str(r.status) != "completed":
            continue
        v = r.steps["summarise"].outputs["output"][0]
        if best is None or v.load()["total"] > best.load()["total"]:
            best = v
    region_report(artifact_version_id=str(best.id))
PY
python region_report.py
