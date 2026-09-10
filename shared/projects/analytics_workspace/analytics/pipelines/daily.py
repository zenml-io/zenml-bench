"""Daily analytics. Run from the analytics project root: `python pipelines/daily.py`."""
from typing import Annotated

import pandas as pd
from zenml import pipeline, step

from src.features import build_features, summarise


@step
def load(path: str = "data/visits.csv") -> Annotated[pd.DataFrame, "visits"]:
    return pd.read_csv(path)


@pipeline
def daily_analytics(path: str = "data/visits.csv") -> None:
    summarise(features=build_features(df=load(path=path)))


if __name__ == "__main__":
    daily_analytics()
