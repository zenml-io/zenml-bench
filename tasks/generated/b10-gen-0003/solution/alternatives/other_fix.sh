#!/usr/bin/env bash
# Alternative: a second valid fix for the same fault.
set -euo pipefail
cd "${APP_DIR:-/app/daily_digest}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    return pd.read_csv(f"data/{date}.csv")'; assert old in s, old
s = s.replace(old, '    return pd.read_csv(f"data/{date}.csv", thousands=",")', 1)
p.write_text(s)
PY
python run.py --date 2026-05-27
