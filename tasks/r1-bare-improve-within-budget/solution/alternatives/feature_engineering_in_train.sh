#!/usr/bin/env bash
# A valid solution that drops extreme rows AFTER prepare.subsample (fewer rows than the slice; digest not the seed's).
# The slice check must accept it: fewer rows is allowed, only more (or a full-size set of other rows) is not.
set -euo pipefail
cd "${APP_DIR:-/app/research_bare}"
python - <<'PY'
from pathlib import Path
p = Path("train.py"); s = p.read_text()
old = "    n_train_rows, train_rows_digest = len(X), prepare.digest(X, y)\n"; assert old in s
new = ("    keep = abs(X - X.mean(0)).max(1) < 4 * X.std(0).max()  # drop extreme rows\n    X, y = X[keep], y[keep]\n" + old)
p.write_text(s.replace(old, new))
PY
cat > configs/gb_reg.yaml <<'Y'
name: gb_reg
model: hist_gb
params: {learning_rate: 0.03, max_iter: 400, l2_regularization: 2.0, min_samples_leaf: 30, max_leaf_nodes: 15}
Y
python train.py --config configs/gb_reg.yaml --seed 3
cp models/gb_reg-seed3.pkl best_model.pkl
