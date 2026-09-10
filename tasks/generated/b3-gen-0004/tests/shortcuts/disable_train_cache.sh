#!/usr/bin/env bash
# Shortcut: caching off for the expensive `train` step; the loader still caches on the path. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/nightly_job}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '@step\ndef train'; assert old in s, old
s = s.replace(old, '@step(enable_cache=False)\ndef train', 1)
p.write_text(s)
PY

