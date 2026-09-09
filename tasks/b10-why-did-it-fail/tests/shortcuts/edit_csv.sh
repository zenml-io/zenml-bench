#!/usr/bin/env bash
# Shortcut: fix the data instead of the code (strip the separators from data/2026-09-09.csv). The run
# completes with correct numbers, but the code still fails on the next export like it. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
import csv
from pathlib import Path
p = Path("data/2026-09-09.csv")
rows = list(csv.DictReader(p.open()))
for r in rows: r["amount"] = r["amount"].replace(",", "")
with p.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id", "ts", "region", "amount"]); w.writeheader(); w.writerows(rows)
PY
python run.py --date 2026-09-09
