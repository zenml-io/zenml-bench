"""Steps for the churn-style training pipeline (written against ZenML 0.4x)."""
from typing import Tuple

import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from zenml.steps import BaseParameters, Output, step

DATA_PATH = "data/train.csv"


class SplitParams(BaseParameters):
    test_size: float = 0.3
    seed: int = 0


class TrainParams(BaseParameters):
    C: float = 1.0
    max_iter: int = 1000


@step
def load_data() -> Output(features=pd.DataFrame, labels=pd.Series):
    df = pd.read_csv(DATA_PATH)
    return df.drop(columns="label"), df["label"]


@step
def split(
    features: pd.DataFrame, labels: pd.Series, params: SplitParams
) -> Output(x_train=pd.DataFrame, x_test=pd.DataFrame, y_train=pd.Series, y_test=pd.Series):
    return train_test_split(features, labels, test_size=params.test_size, random_state=params.seed)


@step
def train(x_train: pd.DataFrame, y_train: pd.Series, params: TrainParams) -> ClassifierMixin:
    return LogisticRegression(C=params.C, max_iter=params.max_iter).fit(x_train, y_train)


@step
def evaluate(model: ClassifierMixin, x_test: pd.DataFrame, y_test: pd.Series) -> Output(score=float):
    return float(model.score(x_test, y_test))
