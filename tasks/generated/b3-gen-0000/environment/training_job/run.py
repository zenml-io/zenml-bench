"""train_nightly: trains a small model every night. Run from this directory: `python run.py`."""
import time
from typing import Annotated

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from zenml import pipeline, step

DATA_PATH = "data/training_set.csv"
LABEL = "y"


@step
def load_rows() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH)


@step
def train(df: pd.DataFrame) -> LogisticRegression:
    time.sleep(3)  # stand-in for real work
    x, y = df.drop(columns=LABEL), df[LABEL]
    return LogisticRegression(max_iter=1000).fit(x, y)


@step
def assess(model: LogisticRegression, df: pd.DataFrame) -> Annotated[float, "val_accuracy"]:
    x, y = df.drop(columns=LABEL), df[LABEL]
    _, x_test, _, y_test = train_test_split(x, y, test_size=0.35, random_state=3)
    score = float(model.score(x_test, y_test))
    print(f"val_accuracy={score:.4f}")
    return score


@pipeline
def train_nightly() -> None:
    df = load_rows()
    model = train(df=df)
    assess(model=model, df=df)


if __name__ == "__main__":
    train_nightly()
