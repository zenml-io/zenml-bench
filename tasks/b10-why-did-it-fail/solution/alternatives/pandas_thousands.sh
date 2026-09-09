#!/usr/bin/env bash
# Alternative: tell the CSV reader about the separator (`thousands=","`), so `load` already yields floats.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    return pd.read_csv(f"data/{date}.csv")'; assert old in s
s = s.replace(old, '    return pd.read_csv(f"data/{date}.csv", thousands=",")')
p.write_text(s)
PY
python run.py --date 2026-09-09
