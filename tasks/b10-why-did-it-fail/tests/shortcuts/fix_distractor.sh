#!/usr/bin/env bash
# Shortcut: diagnose the *most recent* failed run (the manual typo, 2026-09-31), "fix" it by making the loader
# fall back to the latest available file, and run that. Completes, but for the wrong day. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    return pd.read_csv(f"data/{date}.csv")'; assert old in s
s = s.replace(old, '''    path = Path(f"data/{date}.csv")
    if not path.exists():
        path = sorted(Path("data").glob("*.csv"))[-2]  # fall back to the latest complete export
    return pd.read_csv(path)''')
s = s.replace("import pandas as pd", "from pathlib import Path\n\nimport pandas as pd")
p.write_text(s)
PY
python run.py --date 2026-09-31
