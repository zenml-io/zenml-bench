#!/usr/bin/env bash
# Reference. For each backfilled day the most recent COMPLETED processing is the one that counts (finance
# re-processed three days with corrected exports; one re-processing failed and does not supersede). Among
# those, the largest total is the busiest day. Fetch that summary by artifact name and version number, pass it
# into a one-step pipeline, and cite name and version in the report.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
cat > region_report.py <<'PY'
"""Top region of one stored daily summary. Run from this directory: python region_report.py [<artifact-name> <version>]

Without arguments, picks the busiest backfilled day: latest completed `backfill` processing per day, then the largest total."""
import json
import sys
from typing import Any

from zenml import pipeline, step
from zenml.client import Client


@step
def top_region(summary: dict[str, Any], artifact_name: str, artifact_version: str) -> dict[str, Any]:
    region, stats = max(summary["regions"].items(), key=lambda kv: kv[1]["total"])
    out = {"region": region, "total": stats["total"], "artifact_name": artifact_name, "artifact_version": artifact_version}
    with open("reports/region_top.json", "w") as f:
        json.dump(out, f, indent=2)
    return out


@pipeline
def region_report(summary: Any, artifact_name: str, artifact_version: str) -> None:  # `summary` untyped on purpose: a typed pipeline argument only accepts JSON values, not an artifact version
    top_region(summary, artifact_name, artifact_version)


def busiest_backfill_summary() -> tuple[str, str]:
    """(artifact name, version) of the summary that counts for the busiest backfilled day."""
    runs = Client().list_pipeline_runs(pipeline="daily_report", tags=["backfill"], status="completed", sort_by="asc:created", size=100).items
    latest_per_day = {r.steps["load"].config.parameters["date"]: r for r in runs}  # ascending, so the last completed run of a day wins
    versions = [r.steps["summarise"].outputs["output"][0] for r in latest_per_day.values()]
    best = max(versions, key=lambda v: v.load()["total"])
    return best.artifact.name, best.version


if __name__ == "__main__":
    name, version = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else busiest_backfill_summary()
    summary = Client().get_artifact_version(name, version)
    print(f"using {name} v{version} ({summary.id})")
    region_report(summary=summary, artifact_name=name, artifact_version=str(version))
PY
python region_report.py
