"""Shared feature code for the analytics pipelines."""
from typing import Annotated

import pandas as pd
from zenml import step


@step
def build_features(df: pd.DataFrame) -> Annotated[pd.DataFrame, "features"]:
    out = df.copy()
    out["spend_per_visit"] = out["spend"] / out["visits"].clip(lower=1)
    return out


@step
def summarise(features: pd.DataFrame) -> Annotated[dict, "summary"]:
    return {"rows": int(len(features)), "mean_spend_per_visit": round(float(features["spend_per_visit"].mean()), 4)}
