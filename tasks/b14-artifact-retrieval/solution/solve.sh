#!/usr/bin/env bash
# Reference: pick the completed `backfill` run with the largest summary total through the client, then run a
# one-step pipeline that takes that summary artifact version as its input.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
cat > region_report.py <<'PY'
"""Top region of one stored daily summary. Run from this directory: python region_report.py [<artifact-version-id>]

Without an id, picks the completed `backfill` run of `daily_report` with the largest total."""
import json
import sys
from typing import Any

from zenml import pipeline, step
from zenml.client import Client


@step
def top_region(summary: dict[str, Any]) -> dict[str, Any]:
    region, stats = max(summary["regions"].items(), key=lambda kv: kv[1]["total"])
    out = {"region": region, "total": stats["total"]}
    with open("reports/region_top.json", "w") as f:
        json.dump(out, f, indent=2)
    return out


@pipeline
def region_report(summary: Any) -> None:  # untyped/Any on purpose: a typed (dict) pipeline argument only accepts JSON values, not an artifact version
    top_region(summary)


def busiest_backfill_summary() -> Any:
    runs = Client().list_pipeline_runs(pipeline="daily_report", tags=["backfill"], status="completed", size=100).items
    versions = [r.steps["summarise"].outputs["output"][0] for r in runs]
    return max(versions, key=lambda v: v.load()["total"])


if __name__ == "__main__":
    version = Client().get_artifact_version(sys.argv[1]) if len(sys.argv) > 1 else busiest_backfill_summary()
    print(f"using {version.artifact.name} v{version.version} ({version.id})")
    region_report(summary=version)
PY
python region_report.py
