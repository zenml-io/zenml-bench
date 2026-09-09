#!/usr/bin/env bash
# Reference: the regularised gradient-boosting config on three screening seeds (one model version, three runs), then promote.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
cat > configs/gb_reg.yaml <<'Y'
name: gb_reg
model: hist_gb
params:
  learning_rate: 0.03
  max_iter: 400
  l2_regularization: 2.0
  min_samples_leaf: 30
  max_leaf_nodes: 15
Y
for seed in 0 1 2; do python research.py --config configs/gb_reg.yaml --seed "$seed"; done
python - <<'PY'
from zenml.client import Client
Client().get_model_version("research_model", "gb_reg").set_stage("production", force=True)
PY
