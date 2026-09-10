#!/usr/bin/env bash
# Shortcut: loader cache off only. The loader yields a new DataFrame artifact every run (pandas has no content hash), and both the trainer and the evaluator take it as an input, so every downstream step reruns whichever one is expensive. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/nightly_job}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text()
old = '@step\ndef ingest(path: str)'; assert old in s, old
s = s.replace(old, '@step(enable_cache=False)\ndef ingest(path: str)', 1)
p.write_text(s)
PY

