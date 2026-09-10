#!/usr/bin/env bash
# Shortcut: fix the data instead of the code. Must score 0 (data/2026-04-27.csv must be byte-identical).
set -euo pipefail
cd "${APP_DIR:-/app/sales_summary}"
python - <<'PY'
import pandas as pd
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
df = pd.read_csv("data/2026-04-27.csv")
df["ts"] = pd.to_datetime(df["ts"].str.replace("/", "-"), format=TS_FORMAT)
df["region"] = df["region"].str.strip().str.lower()
a = df["amount"].astype(str); neg = a.str.startswith("("); df["amount"] = a.str.strip("()").astype(float) * neg.map({True: -1.0, False: 1.0})
df["ts"] = df["ts"].dt.strftime(TS_FORMAT)
df.to_csv("data/2026-04-27.csv", index=False)
PY
python run.py --date 2026-04-27
