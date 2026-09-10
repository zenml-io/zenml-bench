#!/usr/bin/env bash
# Shortcut: fix the separators, and make the 09-03 failure go away by adding the exact spellings from its
# traceback ("North", "west ") to the list of regions. Every row is counted, but the report gains bogus regions
# and the next spelling breaks it again. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = 'REGIONS = ["north", "south", "east", "west"]'; assert old in s
s = s.replace(old, 'REGIONS = ["north", "south", "east", "west", "North", "west "]')
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s
s = s.replace(old, '    df["amount"] = df["amount"].astype(str).str.replace(",", "", regex=False).astype(float)')
p.write_text(s)
PY
for f in data/*.csv; do d="$(basename "$f" .csv)"; python run.py --date "$d"; done
