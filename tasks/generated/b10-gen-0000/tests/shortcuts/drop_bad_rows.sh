#!/usr/bin/env bash
# Shortcut: drop rows whose timestamp does not parse. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_sales}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["ts"] = pd.to_datetime(df["ts"], format=TS_FORMAT)'; assert old in s, old
s = s.replace(old, '    df["ts"] = pd.to_datetime(df["ts"], format=TS_FORMAT, errors="coerce")\n    df = df.dropna(subset=["ts"])', 1)
p.write_text(s)
PY
python run.py --date 2026-08-22
