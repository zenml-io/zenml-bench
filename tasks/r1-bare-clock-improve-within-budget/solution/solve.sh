#!/usr/bin/env bash
# Reference: one run of the regularised gradient-boosting config on the default seed, then copy its model file.
set -euo pipefail
cd "${APP_DIR:-/app/research_bare}"
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
python train.py --config configs/gb_reg.yaml
cp models/gb_reg-seed0.pkl best_model.pkl
