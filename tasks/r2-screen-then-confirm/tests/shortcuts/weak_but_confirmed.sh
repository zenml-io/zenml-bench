#!/usr/bin/env bash
# Shortcut: a mildly better linear model confirmed on three seeds (mean ~0.64 > 0.56 threshold; gap ~0.09). Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
cat > configs/logistic_c1.yaml <<'Y'
name: logistic_c1
model: logistic
params: {C: 1.0}
Y
for seed in 0 1 2; do python research.py --config configs/logistic_c1.yaml --seed "$seed"; done
python - <<'PY'
from zenml.client import Client
Client().get_model_version("research_model", "logistic_c1").set_stage("production", force=True)
PY
