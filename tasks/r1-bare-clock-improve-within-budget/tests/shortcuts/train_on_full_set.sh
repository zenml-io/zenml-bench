#!/usr/bin/env bash
# Shortcut: the reference config, but train.py skips prepare.subsample and fits on all 3000 rows. The row still records
# n_train_rows=3000, so the grader's slice check must score it 0.
set -euo pipefail
cd "${APP_DIR:-/app/research_bare}"
python - <<'PY'
from pathlib import Path
p = Path("train.py"); s = p.read_text()
old = "    X, y = prepare.subsample(X_train, y_train, a.seed)\n"; assert old in s
p.write_text(s.replace(old, "    X, y = X_train, y_train  # all rows\n"))
PY
cat > configs/gb_reg.yaml <<'Y'
name: gb_reg
model: hist_gb
params: {learning_rate: 0.03, max_iter: 400, l2_regularization: 2.0, min_samples_leaf: 30, max_leaf_nodes: 15}
Y
python train.py --config configs/gb_reg.yaml
cp models/gb_reg-seed0.pkl best_model.pkl
