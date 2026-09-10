#!/usr/bin/env bash
# Reference: the 2026-04-27 export has refunds written as amounts in parentheses, e.g. "(123.45)". Fix `parse`, then produce the missing report.
set -euo pipefail
cd "${APP_DIR:-/app/sales_summary}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["amount"] = df["amount"].astype(float)'; assert old in s, old
s = s.replace(old, '    amount = df["amount"].astype(str)\n    negative = amount.str.startswith("(") & amount.str.endswith(")")\n    df["amount"] = amount.str.strip("()").astype(float) * negative.map({True: -1.0, False: 1.0})', 1)
p.write_text(s)
PY
python run.py --date 2026-04-27
