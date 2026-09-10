#!/usr/bin/env bash
# Reference: three typed steps (prepare -> train -> evaluate) in pipeline `credit_training`; same CLI.
# `prepare` must `return a, b, c, d` literally: a step annotated with a Tuple that returns
# `train_test_split(...)` directly is treated as ONE output (B9 trap).
set -euo pipefail
cd "${APP_DIR:-/app/credit_script}"
cat > train.py <<'PY'
"""Credit-default model training as a ZenML pipeline. Usage: `python train.py [--data data/credit.csv]`."""
import argparse
from typing import Annotated, Tuple

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from zenml import ArtifactConfig, pipeline, step
from zenml.enums import ArtifactType

TARGET = "default"


@step
def prepare(path: str) -> Tuple[
    Annotated[pd.DataFrame, "x_train"], Annotated[pd.DataFrame, "x_test"],
    Annotated[pd.Series, "y_train"], Annotated[pd.Series, "y_test"],
]:
    df = pd.read_csv(path).dropna().copy()
    df["debt_per_account"] = df["debt_ratio"] * df["income"] / (df["n_accounts"] + 1)
    x, y = df.drop(columns=TARGET), df[TARGET]
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.25, random_state=0, stratify=y)
    return x_train, x_test, y_train, y_test


@step
def train(x_train: pd.DataFrame, y_train: pd.Series) -> Annotated[Pipeline, ArtifactConfig(name="model", artifact_type=ArtifactType.MODEL)]:
    model = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(C=0.5, max_iter=2000, random_state=0))])
    return model.fit(x_train, y_train)


@step
def evaluate(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series) -> Annotated[float, "accuracy"]:
    accuracy = float(model.score(x_test, y_test))
    print(f"accuracy={accuracy:.4f}")
    return accuracy


@pipeline
def credit_training(path: str = "data/credit.csv") -> None:
    x_train, x_test, y_train, y_test = prepare(path=path)
    evaluate(model=train(x_train=x_train, y_train=y_train), x_test=x_test, y_test=y_test)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/credit.csv")
    credit_training(path=ap.parse_args().data)
PY
