#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app/nightly}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = "@step\ndef load_data(path: str)"
assert old in s
s = s.replace("from zenml import pipeline, step", "from zenml import pipeline, step\nfrom zenml.config import CachePolicy\nimport hashlib\n\n\ndef data_digest() -> str:\n    return hashlib.sha256(open(DATA_PATH, \"rb\").read()).hexdigest()\n")
s = s.replace(old, "@step(cache_policy=CachePolicy(cache_func=data_digest))\ndef load_data(path: str)")
p.write_text(s)
PY
