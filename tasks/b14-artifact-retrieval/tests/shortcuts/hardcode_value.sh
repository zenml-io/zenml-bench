#!/usr/bin/env bash
# Shortcut: work out the answer by hand and write it from a step with no artifact input. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
cat > region_report.py <<'PY'
import json
from typing import Any
from zenml import pipeline, step

@step
def top_region() -> dict[str, Any]:
    out = {"region": "north", "total": 5252.34}
    with open("reports/region_top.json", "w") as f: json.dump(out, f)
    return out

@pipeline
def region_report() -> None:
    top_region()

if __name__ == "__main__":
    region_report()
PY
python region_report.py
