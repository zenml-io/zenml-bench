#!/usr/bin/env bash
# Alternative: CachePolicy(cache_func=...) returning a new value each call gives the step a never-repeating cache key.
set -euo pipefail
cd "${APP_DIR:-/app/sampling}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
s = s.replace("from zenml import pipeline, step", "import uuid\nfrom zenml import pipeline, step\nfrom zenml.config import CachePolicy\n\n\ndef never_the_same() -> str:\n    return uuid.uuid4().hex\n"); s = s.replace("@step\ndef sample_events", "@step(cache_policy=CachePolicy(cache_func=never_the_same))\ndef sample_events")
p.write_text(s)
PY
