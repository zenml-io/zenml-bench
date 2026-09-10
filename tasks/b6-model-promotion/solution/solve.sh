#!/usr/bin/env bash
# Reference: promote the lowest-val_mae version through the CLI, point the pipeline's Model at the `production`
# stage, and turn caching off for `predict`. The last part matters: the model version is NOT part of ZenML's step
# cache key, so a `predict` step that loads the model from the step context and gets the same batch as before is
# served from cache (from the old version's run) after a promotion changes.
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
assert 'version="latest"' in s and "@step\ndef predict" in s
s = s.replace('version="latest"', 'version="production"').replace("@step\ndef predict", "@step(enable_cache=False)\ndef predict")
p.write_text(s)
PY
python inference.py
