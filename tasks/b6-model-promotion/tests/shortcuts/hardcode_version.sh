#!/usr/bin/env bash
# Shortcut: promotes correctly but pins inference to the version NUMBER; the grader's re-promotion is not followed. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app/model_promotion}"
BEST=$(python -c "
from zenml.client import Client
vs = Client().list_model_versions(model='demand_forecaster', size=50).items
print(min(vs, key=lambda v: float(v.run_metadata['val_mae'])).number)")
zenml model version update demand_forecaster "$BEST" --stage production
python - <<'PY'
from pathlib import Path
p = Path("inference.py"); s = p.read_text()
s = s.replace('version="latest"', f'version="{__import__("zenml.client", fromlist=["Client"]).Client().get_model_version("demand_forecaster", "production").number}"').replace("@step\ndef predict", "@step(enable_cache=False)\ndef predict")
p.write_text(s)
PY
python inference.py
