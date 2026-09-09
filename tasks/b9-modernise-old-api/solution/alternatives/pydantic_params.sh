#!/usr/bin/env bash
# Alternative: keep parameter classes, as pydantic models passed to the steps.
set -euo pipefail
cd "${APP_DIR:-/app/legacy_training}"
cat > steps.py <<'PY'
from typing import Annotated, Tuple

import pandas as pd
from pydantic import BaseModel
from sklearn.base import ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from zenml import step

DATA_PATH = "data/train.csv"


class SplitParams(BaseModel):
    test_size: float = 0.3
    seed: int = 0


class TrainParams(BaseModel):
    C: float = 1.0
    max_iter: int = 1000


@step
def load_data() -> Tuple[Annotated[pd.DataFrame, "features"], Annotated[pd.Series, "labels"]]:
    df = pd.read_csv(DATA_PATH)
    return df.drop(columns="label"), df["label"]


@step
def split(features: pd.DataFrame, labels: pd.Series, params: SplitParams) -> Tuple[
    Annotated[pd.DataFrame, "x_train"], Annotated[pd.DataFrame, "x_test"],
    Annotated[pd.Series, "y_train"], Annotated[pd.Series, "y_test"],
]:
    x_train, x_test, y_train, y_test = train_test_split(features, labels, test_size=params.test_size, random_state=params.seed)
    return x_train, x_test, y_train, y_test


@step
def train(x_train: pd.DataFrame, y_train: pd.Series, params: TrainParams) -> ClassifierMixin:
    return LogisticRegression(C=params.C, max_iter=params.max_iter).fit(x_train, y_train)


@step
def evaluate(model: ClassifierMixin, x_test: pd.DataFrame, y_test: pd.Series) -> Annotated[float, "score"]:
    return float(model.score(x_test, y_test))
PY
cat > run.py <<'PY'
from zenml import pipeline
from zenml.client import Client

from steps import SplitParams, TrainParams, evaluate, load_data, split, train


@pipeline
def training_pipeline() -> None:
    features, labels = load_data()
    x_train, x_test, y_train, y_test = split(features, labels, params=SplitParams(test_size=0.25, seed=0))
    model = train(x_train, y_train, params=TrainParams(C=0.5))
    evaluate(model, x_test, y_test)


if __name__ == "__main__":
    run = training_pipeline()
    print("score:", Client().get_pipeline_run(run.id).steps["evaluate"].outputs["score"][0].load())
PY
