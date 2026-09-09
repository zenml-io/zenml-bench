#!/usr/bin/env bash
# Reference: the 2026-09-09 export contains amounts with a thousands separator ("1,234.50"), which
# `astype(float)` rejects. Strip the separator in `parse`, then produce the missing report.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s
s = s.replace(old, '    df["amount"] = df["amount"].astype(str).str.replace(",", "", regex=False).astype(float)')
p.write_text(s)
PY
python run.py --date 2026-09-09
