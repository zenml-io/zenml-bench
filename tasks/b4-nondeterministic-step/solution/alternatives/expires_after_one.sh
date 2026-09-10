#!/usr/bin/env bash
# Alternative: CachePolicy(expires_after=1): the cached sample is valid for one second, so any real rerun misses. Accepted by outcome (fresh sample per run), though expires_after=0 would NOT work.
set -euo pipefail
cd "${APP_DIR:-/app/sampling}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step", "from zenml import pipeline, step\nfrom zenml.config import CachePolicy"); s = s.replace("@step\ndef sample_events", "@step(cache_policy=CachePolicy(expires_after=1))\ndef sample_events")
p.write_text(s)
PY
