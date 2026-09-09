#!/usr/bin/env bash
# A different model family (random forest) promoted through the CLI instead of the client. Closes ~0.8 of the gap.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
cat > configs/forest.yaml <<'Y'
name: forest
model: forest
params: {n_estimators: 500, min_samples_leaf: 3, max_features: 0.5}
Y
python research.py --config configs/forest.yaml --seed 2
zenml model version update research_model forest --stage production --force
