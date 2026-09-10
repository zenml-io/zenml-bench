#!/usr/bin/env bash
# A valid solution that edits `train`: drop rows the model treats as outliers AFTER prepare.subsample (so it trains on
# fewer rows than the slice, with a digest that is not the seed's) and standardise features. The slice check must
# accept this: fewer rows than the slice is allowed, only more (or a full-size set of other rows) is not.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
python - <<'PY'
from pathlib import Path
p = Path("research.py"); s = p.read_text()
old = "    X, y = prepare.subsample(X_train, y_train, seed)\n"; assert old in s
new = ("    X, y = prepare.subsample(X_train, y_train, seed)\n"
       "    keep = np.abs(X - X.mean(0)).max(1) < 4 * X.std(0).max()  # drop extreme rows\n"
       "    X, y = X[keep], y[keep]\n")
p.write_text(s.replace(old, new))
PY
cat > configs/gb_reg.yaml <<'Y'
name: gb_reg
model: hist_gb
params: {learning_rate: 0.03, max_iter: 400, l2_regularization: 2.0, min_samples_leaf: 30, max_leaf_nodes: 15}
Y
python research.py --config configs/gb_reg.yaml --seed 3
python - <<'PY'
from zenml.client import Client
Client().get_model_version("research_model", "gb_reg").set_stage("production", force=True)
PY
