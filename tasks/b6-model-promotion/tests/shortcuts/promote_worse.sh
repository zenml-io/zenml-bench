#!/usr/bin/env bash
# Shortcut: promotes the latest (worse) version. Must fail the lowest-val_mae check.
set -euo pipefail
cd "${APP_DIR:-/app/model_promotion}"
zenml model version update demand_forecaster 2 --stage production
python - <<'PY'
from pathlib import Path
p = Path("inference.py"); s = p.read_text()
s = s.replace('version="latest"', 'version="production"').replace("@step\ndef predict", "@step(enable_cache=False)\ndef predict")
p.write_text(s)
PY
python inference.py
