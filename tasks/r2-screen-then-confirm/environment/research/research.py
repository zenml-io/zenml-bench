"""Research loop entrypoint. Run from this directory:

    python research.py --config configs/baseline.yaml [--seed 0]

One run = one experiment: prepare_data (cached) -> train(config, seed) -> evaluate. Every run is attached to the
ZenML model `research_model`, version = the config's `name`, so runs of the same config on different seeds
collect under one model version. Promote a version with `zenml model version update research_model <name> -s production`.
"""
import argparse
from pathlib import Path
from typing import Annotated, Any, Tuple

import numpy as np
import yaml
from sklearn.base import BaseEstimator
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from zenml import ArtifactConfig, Model, log_metadata, pipeline, step
from zenml.enums import ArtifactType

import prepare

MODEL_NAME = "research_model"


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


@step
def prepare_data() -> Tuple[
    Annotated[np.ndarray, "X_train"], Annotated[np.ndarray, "y_train"],
    Annotated[np.ndarray, "X_val"], Annotated[np.ndarray, "y_val"],
]:
    X_train, y_train, X_val, y_val = prepare.load_data()
    return X_train, y_train, X_val, y_val


@step
def train(
    X_train: np.ndarray, y_train: np.ndarray, config: dict[str, Any], seed: int
) -> Annotated[BaseEstimator, ArtifactConfig(name="model", artifact_type=ArtifactType.MODEL)]:
    X, y = prepare.subsample(X_train, y_train, seed)
    return build_model(config, seed).fit(X, y)


@step
def evaluate(model: BaseEstimator, X_val: np.ndarray, y_val: np.ndarray) -> Annotated[float, "val_log_loss"]:
    loss = prepare.evaluate(model, X_val, y_val)
    log_metadata({"val_log_loss": loss}, infer_model=True)
    print(f"val_log_loss={loss:.4f}")
    return loss


@pipeline
def research(config: dict[str, Any], seed: int) -> None:
    X_train, y_train, X_val, y_val = prepare_data()
    evaluate(train(X_train, y_train, config, seed), X_val, y_val)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=prepare.SCREENING_SEEDS[0])
    a = ap.parse_args()
    config = yaml.safe_load(a.config.read_text())
    version = config.get("name") or a.config.stem
    research.with_options(model=Model(name=MODEL_NAME, version=version))(config=config, seed=a.seed)


if __name__ == "__main__":
    main()
