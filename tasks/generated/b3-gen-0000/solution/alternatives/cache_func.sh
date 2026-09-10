#!/usr/bin/env bash
# Alternative: CachePolicy(cache_func=<sha256 of the file>) on the loader.
set -euo pipefail
cd "${APP_DIR:-/app/training_job}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = 'from zenml import pipeline, step'; assert old in s, old
s = s.replace(old, 'from zenml import pipeline, step\nfrom zenml.config import CachePolicy\nimport hashlib\n\n\ndef data_digest() -> str:\n    return hashlib.sha256(open(DATA_PATH, "rb").read()).hexdigest()\n', 1)
old = '@step\ndef load_rows()'; assert old in s, old
s = s.replace(old, '@step(cache_policy=CachePolicy(cache_func=data_digest))\ndef load_rows()', 1)
p.write_text(s)
PY

