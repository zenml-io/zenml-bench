#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app/nightly}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = "@pipeline\ndef nightly_training"
assert old in s
s = s.replace(old, "@pipeline(enable_cache=False)\ndef nightly_training")
p.write_text(s)
PY
