"""Daily sales report. Run from this directory:

    python run.py --date YYYY-MM-DD [--trigger scheduled|manual]

Reads data/<date>.csv, types the columns, summarises amounts per region and writes reports/<date>.json.
bin/nightly.sh is what cron runs each morning; runs started by hand default to `--trigger manual`.
"""
import argparse
import json
from typing import Any

import pandas as pd
from zenml import pipeline, step

TS_FORMAT = "%Y-%m-%d %H:%M:%S"
REGIONS = ["north", "south", "east", "west"]  # the regions finance reports on


@step(enable_cache=False)  # always re-read the export: upstream re-delivers corrected files under the same name
def load(date: str) -> pd.DataFrame:
    return pd.read_csv(f"data/{date}.csv")


@step
def parse(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["ts"] = pd.to_datetime(df["ts"], format=TS_FORMAT)
    df["amount"] = df["amount"].astype(float)
    return df


@step
def summarise(df: pd.DataFrame) -> dict[str, Any]:
    regions = {
        region: {"count": int(g.count()), "total": round(float(g.sum()), 2), "mean": round(float(g.mean()), 2)}
        for region, g in df.groupby("region")["amount"]
        if region in REGIONS
    }
    counted = sum(r["count"] for r in regions.values())
    if counted != len(df):  # every row must land in one of finance's regions
        unknown = sorted(set(df["region"]) - set(REGIONS))
        raise ValueError(f"{len(df) - counted} of {len(df)} rows have a region outside {REGIONS}: {unknown}")
    return {"rows": int(len(df)), "total": round(float(df["amount"].sum()), 2), "regions": regions}


@step
def write_report(summary: dict[str, Any], date: str) -> str:
    path = f"reports/{date}.json"
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    return path


@pipeline
def daily_report(date: str) -> None:
    write_report(summarise(parse(load(date))), date)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="day to process, YYYY-MM-DD (reads data/<date>.csv)")
    ap.add_argument("--trigger", choices=["scheduled", "manual"], default="manual")
    args = ap.parse_args()
    run_name = f"scheduled-{args.date}" if args.trigger == "scheduled" else f"manual-{args.date}-{{time}}"
    daily_report.with_options(run_name=run_name, tags=[args.trigger])(date=args.date)
