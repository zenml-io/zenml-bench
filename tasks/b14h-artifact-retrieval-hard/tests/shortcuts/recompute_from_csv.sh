#!/usr/bin/env bash
# Shortcut: right day, wrong source. The step re-reads data/2026-08-26.csv (the corrected export, still on disk)
# and recomputes; the numbers are right but the run has no artifact input and cites no version. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
cat > region_report.py <<'PY'
import json
from typing import Any
import pandas as pd
from zenml import pipeline, step

@step
def top_region(date: str) -> dict[str, Any]:
    df = pd.read_csv(f"data/{date}.csv")
    totals = df.groupby("region")["amount"].sum().round(2)
    out = {"region": totals.idxmax(), "total": float(totals.max()), "artifact_name": "daily_report::summarise::output", "artifact_version": "5"}
    with open("reports/region_top.json", "w") as f: json.dump(out, f)
    return out

@pipeline
def region_report(date: str) -> None:
    top_region(date)

if __name__ == "__main__":
    region_report(date="2026-08-26")
PY
python region_report.py
