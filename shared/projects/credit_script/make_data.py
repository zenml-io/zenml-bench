# /// script
# requires-python = ">=3.14"
# dependencies = ["pandas", "numpy"]
# ///
"""Regenerates data/credit.csv and the grader's hidden fixture for B2. Run here: `uv run make_data.py`."""
import numpy as np
import pandas as pd


def make(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "age": rng.integers(21, 70, n),
        "income": np.round(rng.lognormal(10.3, 0.5, n), 0),
        "debt_ratio": np.round(rng.beta(2, 5, n), 3),
        "n_accounts": rng.integers(0, 12, n),
        "late_payments": rng.poisson(0.7, n),
        "employed": rng.integers(0, 2, n),
    })
    logit = -1.2 + 6 * df["debt_ratio"] + 0.9 * df["late_payments"] - 0.9 * df["employed"] - 0.00003 * df["income"] - 0.01 * df["age"] + rng.normal(0, 0.8, n)
    df["default"] = (logit > 0.4).astype(int)
    return df


make(2400, 11).to_csv("data/credit.csv", index=False)
make(900, 12).to_csv("../../../tasks/b2-script-to-pipeline/tests/fixtures/hidden.csv", index=False)
print("wrote data/credit.csv and hidden.csv")
