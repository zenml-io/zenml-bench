"""Batch inference: `python inference.py [--input data/batch.csv]`. Loads the team's forecaster from the ZenML
model registry and writes predictions as the `predictions` artifact."""
import argparse
from typing import Annotated

import pandas as pd
from zenml import Model, get_step_context, pipeline, step

FEATURES = ["store_id", "promo", "price", "temp_c", "dow"]


@step
def load_batch(path: str) -> Annotated[pd.DataFrame, "batch"]:
    return pd.read_csv(path)


@step
def predict(batch: pd.DataFrame) -> Annotated[pd.DataFrame, "predictions"]:
    model = get_step_context().model.get_model_artifact("model").load()
    out = batch[["store_id"]].copy()
    out["units_pred"] = model.predict(batch[FEATURES]).round(2)
    print(f"predicted {len(out)} rows, mean {out['units_pred'].mean():.2f}")
    return out


@pipeline(model=Model(name="demand_forecaster", version="latest"))
def batch_forecast(input_path: str = "data/batch.csv") -> None:
    predict(batch=load_batch(path=input_path))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/batch.csv")
    batch_forecast(input_path=ap.parse_args().input)
