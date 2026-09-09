#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app/nightly}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = "@step\ndef load_data(path: str)"
assert old in s
s = s.replace(old, "@step(enable_cache=False)\ndef load_data(path: str)")
p.write_text(s)
PY
