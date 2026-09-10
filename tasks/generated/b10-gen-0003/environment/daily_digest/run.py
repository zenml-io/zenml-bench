"""Daily sales report. Run from this directory:

    python run.py --date YYYY-MM-DD [--trigger scheduled|manual]

Reads data/<date>.csv, types the columns, summarises amounts per region and writes reports/<date>.json.
The cron job runs it every morning with `--trigger scheduled`; runs started by hand default to `manual`.
"""
import argparse
import json
from typing import Any

import pandas as pd
from zenml import pipeline, step

TS_FORMAT = "%Y-%m-%d %H:%M:%S"
COLUMNS = ["id", "ts", "region", "amount"]
REGIONS = ["retail", "online", "wholesale", "partner"]


@step
def load(date: str) -> pd.DataFrame:
    return pd.read_csv(f"data/{date}.csv")


@step
def parse(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["ts"] = pd.to_datetime(df["ts"], format=TS_FORMAT)
    df["region"] = df["region"].str.strip().str.lower()
    df["amount"] = df["amount"].astype(float)
    return df


@step
def summarise(df: pd.DataFrame) -> dict[str, Any]:
    regions = {
        region: {"count": int(g.count()), "total": round(float(g.sum()), 2), "mean": round(float(g.mean()), 2)}
        for region, g in df.groupby("region")["amount"]
    }
    ts = pd.to_datetime(df["ts"])  # the DataFrame may have been round-tripped through the artifact store as text
    return {"rows": int(len(df)), "total": round(float(df["amount"].sum()), 2), "regions": regions,
            "span": [ts.min().strftime(TS_FORMAT), ts.max().strftime(TS_FORMAT)]}


@step
def write_report(summary: dict[str, Any], date: str) -> str:
    path = f"reports/{date}.json"
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    return path


@pipeline
def daily_digest(date: str) -> None:
    write_report(summarise(parse(load(date))), date)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="day to process, YYYY-MM-DD (reads data/<date>.csv)")
    ap.add_argument("--trigger", choices=["scheduled", "manual"], default="manual")
    args = ap.parse_args()
    run_name = f"scheduled-{args.date}" if args.trigger == "scheduled" else f"manual-{args.date}-{{time}}"
    daily_digest.with_options(run_name=run_name, tags=[args.trigger])(date=args.date)
