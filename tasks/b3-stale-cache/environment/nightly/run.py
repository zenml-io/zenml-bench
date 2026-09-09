"""Nightly training pipeline. Run from this directory: `uv run python run.py`."""
import time
from typing import Annotated

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from zenml import pipeline, step

DATA_PATH = "data/train.csv"


@step
def load_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@step
def train(df: pd.DataFrame) -> LogisticRegression:
    time.sleep(3)  # stand-in for real training time
    x, y = df.drop(columns="label"), df["label"]
    return LogisticRegression(max_iter=1000).fit(x, y)


@step
def evaluate(model: LogisticRegression, df: pd.DataFrame) -> Annotated[float, "score"]:
    x, y = df.drop(columns="label"), df["label"]
    _, x_test, _, y_test = train_test_split(x, y, test_size=0.3, random_state=0)
    score = float(model.score(x_test, y_test))
    print(f"score={score:.4f}")
    return score


@pipeline
def nightly_training(path: str = DATA_PATH) -> None:
    df = load_data(path=path)
    model = train(df=df)
    evaluate(model=model, df=df)


if __name__ == "__main__":
    nightly_training()
