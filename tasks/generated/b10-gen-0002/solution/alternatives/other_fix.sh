#!/usr/bin/env bash
# Alternative: a second valid fix for the same fault.
set -euo pipefail
cd "${APP_DIR:-/app/daily_digest}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["ts"] = pd.to_datetime(df["ts"], format=TS_FORMAT)'; assert old in s, old
s = s.replace(old, '    df["ts"] = pd.to_datetime(df["ts"], format="mixed")', 1)
p.write_text(s)
PY
python run.py --date 2026-02-11
