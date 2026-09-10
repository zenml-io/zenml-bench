#!/usr/bin/env bash
# Alternative: CachePolicy(cache_func=...) folds the production version id into the cache key, so predict is cached until the promotion changes.
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
s = s.replace("from zenml import Model, get_step_context, pipeline, step", "from zenml import Model, get_step_context, pipeline, step\nfrom zenml.client import Client\nfrom zenml.config import CachePolicy\n\n\ndef production_version_id() -> str:\n    return str(Client().get_model_version(\"demand_forecaster\", \"production\").id)\n")
s = s.replace('version="latest"', 'version="production"').replace("@step\ndef predict", "@step(cache_policy=CachePolicy(cache_func=production_version_id))\ndef predict")
p.write_text(s)
PY
python inference.py
