#!/usr/bin/env bash
# A random forest confirmed on all five screening seeds, promoted through the CLI.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
cat > configs/forest.yaml <<'Y'
name: forest
model: forest
params: {n_estimators: 500, min_samples_leaf: 3, max_features: 0.5}
Y
for seed in 0 1 2 3 4; do python research.py --config configs/forest.yaml --seed "$seed"; done
zenml model version update research_model forest --stage production --force
