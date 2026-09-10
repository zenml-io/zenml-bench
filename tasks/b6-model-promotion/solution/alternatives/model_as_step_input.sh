#!/usr/bin/env bash
# Alternative: the production model artifact is fetched in the pipeline function and passed into predict as an input, so it is part of the cache key and recorded as the step's input (cleanest lineage).
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
s = s.replace("from zenml import Model, get_step_context, pipeline, step", "from zenml import Model, pipeline, step\nfrom zenml.client import Client\nfrom zenml.enums import ModelStages")
s = s.replace("def predict(batch: pd.DataFrame)", "def predict(batch: pd.DataFrame, model: object)")
s = s.replace("    model = get_step_context().model.get_model_artifact(\"model\").load()\n", "")
s = s.replace('version="latest"', 'version="production"')
s = s.replace("predict(batch=load_batch(path=input_path))", "model_av = Client().get_model_version(\"demand_forecaster\", ModelStages.PRODUCTION).get_model_artifact(\"model\")\n    predict(batch=load_batch(path=input_path), model=model_av)")
p.write_text(s)
PY
python inference.py
