#!/usr/bin/env bash
# Shortcut: correct migration but the old parameter values are lost (defaults used). Must fail on the score and params checks.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; bash "$HERE/../../solution/solve.sh"
cd "${APP_DIR:-/app/legacy_training}"
python - <<'PY'
from pathlib import Path
p = Path("run.py"); s = p.read_text(); old = "training_pipeline(test_size=0.25, seed=0, C=0.5)"
assert old in s; p.write_text(s.replace(old, "training_pipeline()"))
PY
