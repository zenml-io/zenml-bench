#!/usr/bin/env bash
# Shortcut: fix the region fault only (the older failure), not this morning's separator fault. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s
s = s.replace(old, '    df["region"] = df["region"].str.strip().str.lower()\n' + old)
p.write_text(s)
PY
for f in data/*.csv; do d="$(basename "$f" .csv)"; python run.py --date "$d"; done
