"""Training pipeline: `python training.py --algorithm linear|forest`. Each run registers a new version of the
ZenML model `demand_forecaster` and records its validation MAE on that version."""
import argparse
from typing import Annotated

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from zenml import ArtifactConfig, Model, log_metadata, pipeline, step
from zenml.enums import ArtifactType

FEATURES = ["store_id", "promo", "price", "temp_c", "dow"]


@step
def load_train(path: str = "data/train.csv") -> tuple[Annotated[pd.DataFrame, "train_df"], Annotated[pd.DataFrame, "val_df"]]:
    df = pd.read_csv(path)
    train, val = train_test_split(df, test_size=0.25, random_state=0)
    return train.reset_index(drop=True), val.reset_index(drop=True)


@step
def train(train_df: pd.DataFrame, algorithm: str) -> Annotated[object, ArtifactConfig(name="model", artifact_type=ArtifactType.MODEL)]:
    est = LinearRegression() if algorithm == "linear" else RandomForestRegressor(n_estimators=30, max_depth=4, random_state=0)
    return est.fit(train_df[FEATURES], train_df["units"])


@step
def evaluate(model: object, val_df: pd.DataFrame) -> Annotated[float, "val_mae"]:
    mae = float(mean_absolute_error(val_df["units"], model.predict(val_df[FEATURES])))
    log_metadata(metadata={"val_mae": mae}, infer_model=True)
    print(f"val_mae={mae:.4f}")
    return mae


@pipeline(model=Model(name="demand_forecaster"))
def train_forecaster(algorithm: str = "linear") -> None:
    train_df, val_df = load_train()
    evaluate(model=train(train_df=train_df, algorithm=algorithm), val_df=val_df)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--algorithm", default="linear", choices=["linear", "forest"])
    train_forecaster(algorithm=ap.parse_args().algorithm)
