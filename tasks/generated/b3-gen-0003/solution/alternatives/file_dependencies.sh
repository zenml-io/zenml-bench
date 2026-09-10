#!/usr/bin/env bash
# Alternative: CachePolicy(file_dependencies=[DATA_PATH]) on the loader.
set -euo pipefail
cd "${APP_DIR:-/app/modeljob}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = 'from zenml import pipeline, step'; assert old in s, old
s = s.replace(old, 'from zenml import pipeline, step\nfrom zenml.config import CachePolicy', 1)
old = '@step\ndef read_dataset(path: str)'; assert old in s, old
s = s.replace(old, '@step(cache_policy=CachePolicy(file_dependencies=[DATA_PATH]))\ndef read_dataset(path: str)', 1)
p.write_text(s)
PY

