#!/usr/bin/env bash
# Reference: the 2026-05-18 export has amounts of 1000 or more written with a thousands separator, e.g. "1,234.50". Fix `parse`, then produce the missing report.
set -euo pipefail
cd "${APP_DIR:-/app/region_digest}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s, old
s = s.replace(old, '    df["amount"] = df["amount"].astype(str).str.replace(",", "", regex=False).astype(float)', 1)
p.write_text(s)
PY
python run.py --date 2026-05-18
