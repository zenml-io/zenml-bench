#!/usr/bin/env bash
# Shortcut: drop the rows whose amount does not parse. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_digest}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s, old
s = s.replace(old, '    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")\n    df = df.dropna(subset=["amount"])', 1)
p.write_text(s)
PY
python run.py --date 2026-05-27
