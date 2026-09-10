#!/usr/bin/env bash
# Shortcut: promotes both; the second promotion (force) archives the better one, so the worse version ends up in production. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app/model_promotion}"
zenml model version update demand_forecaster 1 --stage production
zenml model version update demand_forecaster 2 --stage production --force
python - <<'PY'
from pathlib import Path
p = Path("inference.py"); s = p.read_text()
s = s.replace('version="latest"', 'version="production"').replace("@step\ndef predict", "@step(enable_cache=False)\ndef predict")
p.write_text(s)
PY
python inference.py
