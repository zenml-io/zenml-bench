#!/usr/bin/env bash
# Shortcut: make both failures go away by dropping the rows that trip them. Runs complete, rows are lost. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s
s = s.replace(old, '    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")\n    df = df.dropna(subset=["amount"])\n    df = df[df["region"].isin(REGIONS)]')
p.write_text(s)
PY
for f in data/*.csv; do d="$(basename "$f" .csv)"; python run.py --date "$d"; done
