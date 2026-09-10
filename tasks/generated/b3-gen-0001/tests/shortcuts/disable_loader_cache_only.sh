#!/usr/bin/env bash
# Loader cache off only: the loader reruns and yields a new DataFrame artifact (no content hash for pandas), so the trainer reruns too; the fitted model hashes by content, so an expensive evaluator would still be cached.
set -euo pipefail
cd "${APP_DIR:-/app/training_job}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '@step\ndef load_data()'; assert old in s, old
s = s.replace(old, '@step(enable_cache=False)\ndef load_data()', 1)
p.write_text(s)
PY

