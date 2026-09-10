#!/usr/bin/env bash
# Shortcut: caching off for the whole pipeline. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/modeljob}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '@pipeline\ndef model_refresh'; assert old in s, old
s = s.replace(old, '@pipeline(enable_cache=False)\ndef model_refresh', 1)
p.write_text(s)
PY

