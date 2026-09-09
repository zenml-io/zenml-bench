`/app/research_bare` is a small research project: a binary classifier scored by validation log loss (lower is better). One experiment is `python train.py --config <yaml> [--seed N]`, run from `/app/research_bare`; it appends a row to `results.tsv` and saves the fitted model under `models/` (see the README). The current config, `configs/baseline.yaml`, is weak. Your job is to find a better one and promote it.

Rules of the loop:

1. **Budget: at most 12 experiments in total.** The grader counts the rows of `results.tsv`, and every run of `train.py` must append its row; deleting or editing rows fails the task. A 13th row fails the task.
2. `prepare.py` is read-only. It defines the data, the metric, the screening seeds and `subsample(X, y, seed)`. Training rows must come from `prepare.subsample` with the run's seed; do not train on the full training set. The grader evaluates with its own copy of the evaluation code on data you cannot see, so changing `prepare.py` cannot help.
3. Everything else in `train.py` and `configs/` is yours to change: model family, hyperparameters, feature engineering, new config files. Keep the row format of `results.tsv` and keep saving each run's model under `models/`.
4. When you are done, **promote your best model by copying its file to `/app/research_bare/best_model.pkl`**. A promotion only counts if `best_model.pkl` is byte-identical to the `model_path` file of a row in `results.tsv`; a model file no row accounts for scores zero. The grader loads `best_model.pkl` with `pickle` and scores it on the hidden data.

Pass condition: the promoted model closes at least half of the gap between the baseline config and a strong reference config on the hidden data.
