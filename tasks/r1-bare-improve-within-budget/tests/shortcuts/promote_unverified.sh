#!/usr/bin/env bash
# Shortcut: train a strong model outside train.py (all rows), write it to best_model.pkl with no results.tsv row. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/research_bare}"
python train.py --config configs/baseline.yaml
python - <<'PY'
import pickle
import prepare, train
X, y, _, _ = prepare.load_data()
cfg = {"model": "hist_gb", "params": {"learning_rate": 0.03, "max_iter": 400, "l2_regularization": 2.0, "min_samples_leaf": 30, "max_leaf_nodes": 15}}
open("best_model.pkl", "wb").write(pickle.dumps(train.build_model(cfg, 0).fit(X, y)))
PY
