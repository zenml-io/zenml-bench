#!/usr/bin/env bash
# Shortcut: caching off for the whole pipeline; the loader reruns every time. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app/sampling}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("@pipeline\ndef qa_sampling", "@pipeline(enable_cache=False)\ndef qa_sampling")
p.write_text(s)
PY
