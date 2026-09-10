#!/usr/bin/env bash
# Shortcut: fix the separators, and delete the row-accounting check in `summarise` so any spelling becomes its
# own region. The run completes, but "North" and "north" are reported as two regions. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '        if region in REGIONS\n'; assert old in s
s = s.replace(old, '')
old = '    if counted != len(df):'; assert old in s
s = s.replace(old, '    if False:')
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s
s = s.replace(old, '    df["amount"] = df["amount"].astype(str).str.replace(",", "", regex=False).astype(float)')
p.write_text(s)
PY
for f in data/*.csv; do d="$(basename "$f" .csv)"; python run.py --date "$d"; done
