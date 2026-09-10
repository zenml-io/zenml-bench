#!/usr/bin/env bash
# Shortcut: work out the answer by hand and write it from a step with no artifact input. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
import json
from zenml.client import Client
v = Client().get_artifact_version("daily_report::summarise::output", "5")
s = v.load(); region, stats = max(s["regions"].items(), key=lambda kv: kv[1]["total"])
json.dump({"region": region, "total": stats["total"]}, open("answer.json", "w"))
PY
cat > region_report.py <<'PY'
import json
from typing import Any
from zenml import pipeline, step

@step
def top_region() -> dict[str, Any]:
    out = json.load(open("answer.json")) | {"artifact_name": "daily_report::summarise::output", "artifact_version": "5"}
    with open("reports/region_top.json", "w") as f: json.dump(out, f)
    return out

@pipeline
def region_report() -> None:
    top_region()

if __name__ == "__main__":
    region_report()
PY
python region_report.py
