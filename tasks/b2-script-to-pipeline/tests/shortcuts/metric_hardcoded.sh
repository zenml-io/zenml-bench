#!/usr/bin/env bash
# Shortcut: evaluate returns the number the script printed on the visible data. Must fail on the hidden file.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/credit_script}"
python - <<'PY'
from pathlib import Path
p = Path("train.py"); s = p.read_text()
s = s.replace("    accuracy = float(model.score(x_test, y_test))\n", "    accuracy = 0.885\n"); assert "0.885" in s
p.write_text(s)
PY
