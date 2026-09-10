#!/usr/bin/env bash
# Shortcut: caching off for the expensive `assess` step; the loader still caches on the path. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/overnight}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '@step\ndef assess'; assert old in s, old
s = s.replace(old, '@step(enable_cache=False)\ndef assess', 1)
p.write_text(s)
PY

