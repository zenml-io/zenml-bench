#!/usr/bin/env bash
# Reference. Two data faults broke scheduled runs this week, both recorded on the failed step's exception_info:
#  - 2026-09-09 (this morning): amounts with a thousands separator ("1,234.50") -> ValueError in `parse`
#  - 2026-09-03: region names capitalised / padded ("North", "west ") -> ValueError in `summarise`
# Neither export is on disk any more. Fix both in `parse`, then prove the fix on every day still in data/.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s
s = s.replace(old, '    df["region"] = df["region"].str.strip().str.lower()\n'
                   '    df["amount"] = df["amount"].astype(str).str.replace(",", "", regex=False).astype(float)')
p.write_text(s)
PY
for f in data/*.csv; do d="$(basename "$f" .csv)"; python run.py --date "$d"; done
