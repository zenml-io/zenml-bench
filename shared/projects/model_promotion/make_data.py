# /// script
# requires-python = ">=3.14"
# dependencies = ["pandas", "numpy"]
# ///
"""Regenerates data/train.csv, data/batch.csv and the grader's hidden batch (tests/fixtures of B6). Run here: `uv run make_data.py`."""
import numpy as np
import pandas as pd

def make(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "store_id": rng.integers(1, 40, n),
        "promo": rng.integers(0, 2, n),
        "price": np.round(rng.uniform(2.0, 9.0, n), 2),
        "temp_c": np.round(rng.normal(15, 8, n), 1),
        "dow": rng.integers(0, 7, n),
    })
    df["units"] = np.round(120 - 9.5 * df["price"] + 25 * df["promo"] + 0.8 * df["temp_c"] + 3 * (df["dow"] >= 5) + rng.normal(0, 6, n), 1)
    return df

make(1200, 7).to_csv("data/train.csv", index=False)
make(60, 8).drop(columns="units").to_csv("data/batch.csv", index=False)
make(45, 9).drop(columns="units").to_csv("../../../tasks/b6-model-promotion/tests/fixtures/hidden_batch.csv", index=False)
print("wrote train/batch/hidden")
