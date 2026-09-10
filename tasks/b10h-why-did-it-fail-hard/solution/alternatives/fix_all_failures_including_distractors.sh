#!/usr/bin/env bash
# Alternative: a thorough agent that also hardens the two non-data failures (missing reports/ directory, ISO
# timestamps in the old manual export) on top of the reference. Harmless; must still score 1.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/daily_report}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '    df["ts"] = pd.to_datetime(df["ts"], format=TS_FORMAT)'; assert old in s
s = s.replace(old, '    df["ts"] = pd.to_datetime(df["ts"], format="ISO8601")')
old = '    path = f"reports/{date}.json"'; assert old in s
s = s.replace(old, '    os.makedirs("reports", exist_ok=True)\n    path = f"reports/{date}.json"')
s = s.replace("import json\n", "import json\nimport os\n", 1)
p.write_text(s)
PY
python run.py --date 2026-09-08
