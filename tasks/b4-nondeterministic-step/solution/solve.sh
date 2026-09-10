#!/usr/bin/env bash
# Reference: enable_cache=False on the sampling step only. The loader keeps the default policy and stays cached;
# review_report reruns by itself because its input is a new DataFrame artifact each run (pandas has no content hash).
set -euo pipefail
cd "${APP_DIR:-/app/sampling}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = "@step\ndef sample_events"; assert old in s
p.write_text(s.replace(old, "@step(enable_cache=False)\ndef sample_events"))
PY
