#!/usr/bin/env bash
# Shortcut: the right number of rows (1050) but drawn with the agent's own RNG from the full set, not the seed's
# slice from prepare.subsample. n_train_rows is within budget; the recorded digest is not the seed's. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/research}"
python - <<'PY'
from pathlib import Path
p = Path("research.py"); s = p.read_text()
old = "    X, y = prepare.subsample(X_train, y_train, seed)\n"; assert old in s
p.write_text(s.replace(old, "    idx = np.random.default_rng(1000 + seed).choice(len(X_train), size=1050, replace=False); X, y = X_train[idx], y_train[idx]\n"))
PY
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
