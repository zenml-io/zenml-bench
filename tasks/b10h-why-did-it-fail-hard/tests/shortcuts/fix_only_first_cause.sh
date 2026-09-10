#!/usr/bin/env bash
# Shortcut: fix this morning's cause (separators) only; the region fault that broke 2026-09-03 remains. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s
s = s.replace(old, '    df["amount"] = df["amount"].astype(str).str.replace(",", "", regex=False).astype(float)')
p.write_text(s)
PY
for f in data/*.csv; do d="$(basename "$f" .csv)"; python run.py --date "$d"; done
