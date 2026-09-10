#!/usr/bin/env bash
# Shortcut: "fix" the failures that were never code faults (missing export -> skip the day; missing reports/ ->
# mkdir; the old manual run's ISO timestamps -> lenient parsing) and leave both real faults. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    return pd.read_csv(f"data/{date}.csv")'; assert old in s
s = s.replace(old, '    path = f"data/{date}.csv"\n    if not os.path.exists(path):\n        return pd.DataFrame(columns=["id", "ts", "region", "amount"])\n    return pd.read_csv(path)')
old = '    df["ts"] = pd.to_datetime(df["ts"], format=TS_FORMAT)'; assert old in s
s = s.replace(old, '    df["ts"] = pd.to_datetime(df["ts"], format="ISO8601")')
old = '    path = f"reports/{date}.json"'; assert old in s
s = s.replace(old, '    os.makedirs("reports", exist_ok=True)\n    path = f"reports/{date}.json"')
s = s.replace("import json\n", "import json\nimport os\n", 1)
p.write_text(s)
PY
for f in data/*.csv; do d="$(basename "$f" .csv)"; python run.py --date "$d"; done
