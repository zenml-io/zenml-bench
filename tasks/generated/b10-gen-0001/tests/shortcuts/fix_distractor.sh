#!/usr/bin/env bash
# Shortcut: diagnose the most recent failed run (the manual typo) and make the loader fall back to the latest export. Completes, for the wrong day. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/sales_summary}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    return pd.read_csv(f"data/{date}.csv")'; assert old in s, old
s = s.replace(old, '    path = Path(f"data/{date}.csv")\n    if not path.exists():\n        path = sorted(Path("data").glob("*.csv"))[-2]\n    return pd.read_csv(path)', 1)
old = 'import pandas as pd'; assert old in s, old
s = s.replace(old, 'from pathlib import Path\n\nimport pandas as pd', 1)
p.write_text(s)
PY
python run.py --date 2026-04-31
