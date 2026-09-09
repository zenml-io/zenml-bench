#!/usr/bin/env bash
# What a careful agent does: screen three configs on three seeds each (9 runs), pick the best by mean
# recorded val_log_loss read back from the store, promote that version. Stays inside the 12-run budget.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
cat > configs/logistic_c1.yaml <<'Y'
name: logistic_c1
model: logistic
params: {C: 1.0}
Y
cat > configs/forest.yaml <<'Y'
name: forest
model: forest
params: {n_estimators: 200, min_samples_leaf: 2}
Y
cat > configs/gb.yaml <<'Y'
name: gb
model: hist_gb
params: {learning_rate: 0.05, max_iter: 300, l2_regularization: 1.0, min_samples_leaf: 20}
Y
for cfg in logistic_c1 forest gb; do for seed in 0 1 2; do python research.py --config "configs/$cfg.yaml" --seed "$seed"; done; done
python - <<'PY'
from statistics import mean
from zenml.client import Client
c = Client()
best = None
for mv in c.list_model_versions(model_name_or_id="research_model", hydrate=True).items:
    runs = [r for r in mv.pipeline_runs.values() if "evaluate" in r.steps]
    if not runs:
        continue
    m = mean(r.steps["evaluate"].outputs["val_log_loss"][0].load() for r in runs)
    print(mv.name, len(runs), round(m, 4))
    best = (m, mv.name) if best is None or m < best[0] else best
print("promoting", best)
c.get_model_version("research_model", best[1]).set_stage("production", force=True)
PY
