"""Backfill job. Run from this directory: `cd jobs/backfill && python run.py`."""
import sys
from pathlib import Path
from typing import Annotated

import pandas as pd
from zenml import pipeline, step

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))  # so that `src` imports when launched from here

from src.features import build_features, summarise  # noqa: E402


@step
def load_history(path: str) -> Annotated[pd.DataFrame, "history"]:
    return pd.read_csv(path)


@pipeline
def backfill_analytics(path: str = str(PROJECT_ROOT / "data" / "visits.csv")) -> None:
    summarise(features=build_features(df=load_history(path=path)))


if __name__ == "__main__":
    backfill_analytics()
