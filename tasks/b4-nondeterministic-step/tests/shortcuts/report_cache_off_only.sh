#!/usr/bin/env bash
# Shortcut: caching disabled on review_report instead of the sampler; the report re-summarises the same cached sample. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app/sampling}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("@step\ndef review_report", "@step(enable_cache=False)\ndef review_report")
p.write_text(s)
PY
