"""Credit-default model training. Usage: `python train.py [--data data/credit.csv]`.

Prepares the data, trains the classifier, evaluates it and prints the accuracy.
"""
import argparse

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

TARGET = "default"


def prepare(df: pd.DataFrame):
    df = df.dropna().copy()
    df["debt_per_account"] = df["debt_ratio"] * df["income"] / (df["n_accounts"] + 1)
    x, y = df.drop(columns=TARGET), df[TARGET]
    return train_test_split(x, y, test_size=0.25, random_state=0, stratify=y)


def train(x_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    model = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(C=0.5, max_iter=2000, random_state=0))])
    return model.fit(x_train, y_train)


def evaluate(model: Pipeline, x_test: pd.DataFrame, y_test: pd.Series) -> float:
    return float(model.score(x_test, y_test))


def main(path: str) -> float:
    x_train, x_test, y_train, y_test = prepare(pd.read_csv(path))
    model = train(x_train, y_train)
    accuracy = evaluate(model, x_test, y_test)
    print(f"accuracy={accuracy:.4f}")
    return accuracy


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/credit.csv")
    main(ap.parse_args().data)
