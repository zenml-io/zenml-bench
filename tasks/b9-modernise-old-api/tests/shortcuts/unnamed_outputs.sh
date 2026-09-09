#!/usr/bin/env bash
# Shortcut: correct migration but the named outputs become output_0, output_1, ... Must fail the output-name check.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; bash "$HERE/../../solution/solve.sh"
cd "${APP_DIR:-/app/legacy_training}"
python - <<'PY'
import re
from pathlib import Path
p = Path("steps.py"); s = p.read_text()
s2 = re.sub(r'Annotated\[(pd\.DataFrame|pd\.Series), "[a-z_]+"\]', r"\1", s)
assert s2 != s; p.write_text(s2)
PY
