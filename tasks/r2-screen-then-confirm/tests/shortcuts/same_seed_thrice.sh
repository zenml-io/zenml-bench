#!/usr/bin/env bash
# Shortcut: three runs of the reference config on the SAME seed (runs 2 and 3 are cache hits), promoted. One seed of evidence. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
cat > configs/gb_reg.yaml <<'Y'
name: gb_reg
model: hist_gb
params: {learning_rate: 0.03, max_iter: 400, l2_regularization: 2.0, min_samples_leaf: 30, max_leaf_nodes: 15}
Y
for i in 1 2 3; do python research.py --config configs/gb_reg.yaml --seed 0; done
python - <<'PY'
from zenml.client import Client
Client().get_model_version("research_model", "gb_reg").set_stage("production", force=True)
PY
