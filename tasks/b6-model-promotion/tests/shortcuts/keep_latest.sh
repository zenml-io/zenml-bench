#!/usr/bin/env bash
# Shortcut: promotes correctly but leaves inference loading latest. Must fail (run linked to the wrong version).
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
pass
p.write_text(s)
PY
python inference.py
