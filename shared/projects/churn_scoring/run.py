"""Nightly churn training. Run from this directory: `python run.py`."""
from typing import Annotated

import pandas as pd
from sklearn.linear_model import LogisticRegression
from zenml import pipeline, step

from scorer import ChurnScorer

FEATURES = ["f0", "f1", "f2", "f3", "f4"]  # f5..f7 are deliberately excluded (leakage)


@step
def load_data() -> pd.DataFrame:
    return pd.read_csv("data/train.csv")


@step
def train(df: pd.DataFrame) -> ChurnScorer:
    model = LogisticRegression(max_iter=1000).fit(df[FEATURES], df["label"])
    return ChurnScorer(model=model, features=FEATURES, threshold=0.6)


@step
def evaluate(scorer: ChurnScorer, df: pd.DataFrame) -> Annotated[float, "flag_rate"]:
    flags = scorer.flag(df)
    rate = sum(flags) / len(flags)
    print(f"flag_rate={rate:.4f}")
    return rate


@pipeline
def churn_training() -> None:
    df = load_data()
    evaluate(train(df), df)


if __name__ == "__main__":
    churn_training()
