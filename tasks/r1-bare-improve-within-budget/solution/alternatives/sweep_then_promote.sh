#!/usr/bin/env bash
# Screen three configs on three seeds (9 rows), pick the best by mean val_log_loss from results.tsv, promote its newest model.
set -euo pipefail
cd "${APP_DIR:-/app/research_bare}"
printf 'name: logistic_c1\nmodel: logistic\nparams: {C: 1.0}\n' > configs/logistic_c1.yaml
printf 'name: forest\nmodel: forest\nparams: {n_estimators: 200, min_samples_leaf: 2}\n' > configs/forest.yaml
printf 'name: gb\nmodel: hist_gb\nparams: {learning_rate: 0.05, max_iter: 300, l2_regularization: 1.0, min_samples_leaf: 20}\n' > configs/gb.yaml
for cfg in logistic_c1 forest gb; do for seed in 0 1 2; do python train.py --config "configs/$cfg.yaml" --seed "$seed"; done; done
python - <<'PY'
import csv, shutil
from collections import defaultdict
from statistics import mean
rows = list(csv.DictReader(open("results.tsv"), delimiter="\t"))
by = defaultdict(list)
for r in rows: by[r["name"]].append(r)
best = min(by, key=lambda n: mean(float(r["val_log_loss"]) for r in by[n]))
print("promoting", best, {n: round(mean(float(r["val_log_loss"]) for r in rs), 4) for n, rs in by.items()})
shutil.copy(by[best][-1]["model_path"], "best_model.pkl")
PY
