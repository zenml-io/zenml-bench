#!/usr/bin/env bash
# Shortcut: caching disabled on the loader as well as the sampler. Must fail (loader re-executes).
set -euo pipefail
cd "${APP_DIR:-/app/sampling}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("@step\ndef load_events", "@step(enable_cache=False)\ndef load_events").replace("@step\ndef sample_events", "@step(enable_cache=False)\ndef sample_events")
p.write_text(s)
PY
