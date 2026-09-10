#!/usr/bin/env bash
# Shortcut: CachePolicy(expires_after=0) looks like 'expire immediately' but 0 is treated as unset; the step stays cached. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app/sampling}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step", "from zenml import pipeline, step\nfrom zenml.config import CachePolicy"); s = s.replace("@step\ndef sample_events", "@step(cache_policy=CachePolicy(expires_after=0))\ndef sample_events")
p.write_text(s)
PY
