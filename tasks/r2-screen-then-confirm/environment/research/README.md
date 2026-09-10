# research: a tiny research loop with ZenML as the lab notebook

Binary classification, 20 features, 3000 training rows, 1000 validation rows. The metric is validation log loss (lower is better).

Files:

- `prepare.py` (read-only): data loading, `subsample(X, y, seed)`, `digest(X, y)`, `evaluate(model, X, y)`, `SCREENING_SEEDS`.
- `research.py`: the ZenML pipeline `research` with steps `prepare_data` (cached), `train(config, seed)`, `evaluate`. `build_model` maps a config to a scikit-learn estimator. Edit freely, but keep `train`'s two bookkeeping outputs `n_train_rows` and `train_rows_digest`: they record which rows the run fitted on (the seed's `prepare.subsample` slice) and are read back from the store as evidence.
- `configs/*.yaml`: one file per experiment config. `name` becomes the ZenML model version.

## One experiment

```bash
python research.py --config configs/baseline.yaml            # seed 0
python research.py --config configs/baseline.yaml --seed 3
```

Every run attaches to the ZenML model `research_model`, version = the config's `name`. Running the same config on another seed attaches a second run (and a second `model` artifact) to the same version, so a version collects the evidence for one config.

## Reading the notebook

```python
from zenml.client import Client
c = Client()
for mv in c.list_model_versions(model_name_or_id="research_model", hydrate=True).items:
    runs = mv.pipeline_runs.values()
    losses = [r.steps["evaluate"].outputs["val_log_loss"][0].load() for r in runs if "evaluate" in r.steps]
    seeds = [r.steps["train"].config.parameters["seed"] for r in runs]
    rows = [r.steps["train"].outputs["n_train_rows"][0].load() for r in runs if "train" in r.steps]
    print(mv.name, mv.stage, seeds, losses, rows)
```

`mv.run_metadata["val_log_loss"]` holds only the most recent run's value; per-run values live on each run's `evaluate` output. `mv.get_model_artifact("model")` returns the most recently produced model artifact of that version; `.load()` gives the fitted estimator.

CLI: `zenml model version list --model research_model` (shows numbers and stages, not names) and `zenml pipeline runs list`.

## Promoting

```bash
zenml model version update research_model <version-name> --stage production --force
```

or `Client().get_model_version("research_model", "<version-name>").set_stage("production", force=True)`. Only one version can be in `production`; promoting another one moves the previous one to `archived`. Read it back with `Client().get_model_version("research_model", "production")`.
