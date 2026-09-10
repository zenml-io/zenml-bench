# research_bare: the same research loop with no framework

Binary classification, 20 features, 3000 training rows, 1000 validation rows. The metric is validation log loss (lower is better).

Files:

- `prepare.py` (read-only): data loading, `subsample(X, y, seed)`, `digest(X, y)`, `evaluate(model, X, y)`, `SCREENING_SEEDS`.
- `train.py`: one experiment per invocation. `build_model` maps a config to a scikit-learn estimator. Edit freely.
- `configs/*.yaml`: one file per experiment config; `name` labels the rows and model files.
- `results.tsv`: the lab notebook. One row per run: `name, seed, val_log_loss, model_path, n_train_rows, train_rows_digest, config`. Created on the first run. `n_train_rows` and `train_rows_digest` record which rows the run fitted on (the seed's `prepare.subsample` slice); keep writing them, they are the run's evidence.
- `models/<name>-seed<seed>.pkl`: the fitted model of each run (pickle).

## One experiment

```bash
python train.py --config configs/baseline.yaml            # seed 0
python train.py --config configs/baseline.yaml --seed 3
```

## Promoting

Copy the model file of the run you choose to `best_model.pkl` in this directory:

```bash
cp models/forest-seed2.pkl best_model.pkl
```
