#!/usr/bin/env bash
# probe: a fix that breaks the normal day (.str on a float column)
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s
s = s.replace(old, '    df["amount"] = df["amount"].str.replace(",", "").astype(float)')
p.write_text(s)
PY
python run.py --date 2026-09-09
