#!/usr/bin/env bash
# Reference: plain-argument parameters, Tuple[Annotated[...]] outputs, pipeline calls steps directly, Client for post-execution.
set -euo pipefail
cd "${APP_DIR:-/app/legacy_training}"
cat > steps.py <<'PY'
"""Steps for the churn-style training pipeline."""
from typing import Annotated, Tuple

import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from zenml import step

DATA_PATH = "data/train.csv"


@step
def load_data() -> Tuple[Annotated[pd.DataFrame, "features"], Annotated[pd.Series, "labels"]]:
    df = pd.read_csv(DATA_PATH)
    return df.drop(columns="label"), df["label"]


@step
def split(
    features: pd.DataFrame, labels: pd.Series, test_size: float = 0.3, seed: int = 0
) -> Tuple[
    Annotated[pd.DataFrame, "x_train"], Annotated[pd.DataFrame, "x_test"],
    Annotated[pd.Series, "y_train"], Annotated[pd.Series, "y_test"],
]:
    x_train, x_test, y_train, y_test = train_test_split(features, labels, test_size=test_size, random_state=seed)
    return x_train, x_test, y_train, y_test


@step
def train(x_train: pd.DataFrame, y_train: pd.Series, C: float = 1.0, max_iter: int = 1000) -> ClassifierMixin:
    return LogisticRegression(C=C, max_iter=max_iter).fit(x_train, y_train)


@step
def evaluate(model: ClassifierMixin, x_test: pd.DataFrame, y_test: pd.Series) -> Annotated[float, "score"]:
    return float(model.score(x_test, y_test))
PY
cat > run.py <<'PY'
"""Entrypoint. Run from this directory: `python run.py`. Prints the evaluation score of the run it just made."""
from zenml import pipeline
from zenml.client import Client

from steps import evaluate, load_data, split, train


@pipeline
def training_pipeline(test_size: float = 0.3, seed: int = 0, C: float = 1.0) -> None:
    features, labels = load_data()
    x_train, x_test, y_train, y_test = split(features, labels, test_size=test_size, seed=seed)
    model = train(x_train, y_train, C=C)
    evaluate(model, x_test, y_test)


if __name__ == "__main__":
    run = training_pipeline(test_size=0.25, seed=0, C=0.5)
    latest = Client().get_pipeline_run(run.id)
    print("score:", latest.steps["evaluate"].outputs["score"][0].load())
PY
