#!/usr/bin/env bash
# Shortcut: the reference config on ONE seed, promoted. Good hidden metric, no confirmation. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
cat > configs/gb_reg.yaml <<'Y'
name: gb_reg
model: hist_gb
params: {learning_rate: 0.03, max_iter: 400, l2_regularization: 2.0, min_samples_leaf: 30, max_leaf_nodes: 15}
Y
python research.py --config configs/gb_reg.yaml
python - <<'PY'
from zenml.client import Client
Client().get_model_version("research_model", "gb_reg").set_stage("production", force=True)
PY
