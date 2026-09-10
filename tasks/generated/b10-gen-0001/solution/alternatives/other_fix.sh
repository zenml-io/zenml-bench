#!/usr/bin/env bash
# Alternative: a second valid fix for the same fault.
set -euo pipefail
cd "${APP_DIR:-/app/sales_summary}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s, old
s = s.replace(old, '    df["amount"] = df["amount"].astype(str).str.replace(r"^\\((.*)\\)$", r"-\\1", regex=True).astype(float)', 1)
p.write_text(s)
PY
python run.py --date 2026-04-27
