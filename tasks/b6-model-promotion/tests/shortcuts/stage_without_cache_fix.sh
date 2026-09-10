#!/usr/bin/env bash
# Shortcut: promotes correctly and switches to the production stage, but predict keeps the default cache policy. The run is linked to the production version while predict is served from the earlier (latest-version) run's cache: lineage says one thing, predictions another. Must fail.
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
s = s.replace('version="latest"', 'version="production"')
p.write_text(s)
PY
python inference.py
