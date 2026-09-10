#!/usr/bin/env bash
# Reference: the 2026-08-22 export has timestamps written with slashes, e.g. "2026/09/09 13:17:08". Fix `parse`, then produce the missing report.
set -euo pipefail
cd "${APP_DIR:-/app/daily_sales}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["ts"] = pd.to_datetime(df["ts"], format=TS_FORMAT)'; assert old in s, old
s = s.replace(old, '    df["ts"] = pd.to_datetime(df["ts"].str.replace("/", "-", regex=False), format=TS_FORMAT)', 1)
p.write_text(s)
PY
python run.py --date 2026-08-22
