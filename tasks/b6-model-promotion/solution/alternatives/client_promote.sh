#!/usr/bin/env bash
# Alternative: promotion through the Python client (set_stage) and ModelStages enum in the pipeline config.
set -euo pipefail
cd "${APP_DIR:-/app/model_promotion}"
python -c "
from zenml.client import Client
vs = Client().list_model_versions(model='demand_forecaster', size=50).items
min(vs, key=lambda v: float(v.run_metadata['val_mae'])).set_stage('production')"
python - <<'PY'
from pathlib import Path
p = Path("inference.py"); s = p.read_text()
s = s.replace("from zenml import Model, get_step_context, pipeline, step", "from zenml import Model, get_step_context, pipeline, step\nfrom zenml.enums import ModelStages")
s = s.replace('version="latest"', "version=ModelStages.PRODUCTION").replace("@step\ndef predict", "@step(enable_cache=False)\ndef predict")
p.write_text(s)
PY
python inference.py
