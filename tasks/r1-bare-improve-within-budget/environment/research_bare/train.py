"""Research loop entrypoint (no framework). Run from this directory:

    python train.py --config configs/baseline.yaml [--seed 0]

One run = one experiment: load data -> subsample by seed -> fit -> validation log loss. Each run saves its fitted
model to models/<name>-seed<seed>.pkl and appends one row to results.tsv (the lab notebook):
name, seed, val_log_loss, model_path, config (JSON). To promote a model, copy its file to best_model.pkl.
"""
import argparse
import json
import pickle
from pathlib import Path
from typing import Any

import yaml
from sklearn.base import BaseEstimator
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

import prepare

RESULTS = Path("results.tsv")
HEADER = "name\tseed\tval_log_loss\tmodel_path\tconfig\n"


def build_model(config: dict[str, Any], seed: int) -> BaseEstimator:
    """Turn a config dict into an unfitted scikit-learn estimator. Edit freely."""
    kind, params = config.get("model", "logistic"), dict(config.get("params", {}))
    if kind == "logistic":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, **params))
    if kind == "tree":
        return DecisionTreeClassifier(random_state=seed, **params)
    if kind == "forest":
        return RandomForestClassifier(random_state=seed, **params)
    if kind == "hist_gb":
        return HistGradientBoostingClassifier(random_state=seed, **params)
    raise ValueError(f"unknown model kind {kind!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=prepare.SCREENING_SEEDS[0])
    a = ap.parse_args()
    config = yaml.safe_load(a.config.read_text())
    name = config.get("name") or a.config.stem
    X_train, y_train, X_val, y_val = prepare.load_data()
    X, y = prepare.subsample(X_train, y_train, a.seed)
    model = build_model(config, a.seed).fit(X, y)
    loss = prepare.evaluate(model, X_val, y_val)
    out = Path("models") / f"{name}-seed{a.seed}.pkl"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(pickle.dumps(model))
    if not RESULTS.exists():
        RESULTS.write_text(HEADER)
    with RESULTS.open("a") as f:
        f.write(f"{name}\t{a.seed}\t{loss:.6f}\t{out}\t{json.dumps(config, sort_keys=True)}\n")
    print(f"val_log_loss={loss:.4f} saved={out}")


if __name__ == "__main__":
    main()
