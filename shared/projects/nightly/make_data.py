# /// script
# requires-python = ">=3.14"
# dependencies = ["pandas", "scikit-learn"]
# ///
"""Generate the fixture datasets for the nightly project.

Each fixture is a small binary classification problem with a different amount of
label noise, so a model trained on each one gets a clearly different score.
"""
from pathlib import Path

import pandas as pd
from sklearn.datasets import make_classification

FIXTURES: dict[str, tuple[int, float]] = {"a": (0, 0.02), "b": (1, 0.15), "c": (2, 0.30)}


def make_fixture(seed: int, noise: float) -> pd.DataFrame:
    x, y = make_classification(n_samples=600, n_features=8, n_informative=5, flip_y=noise, random_state=seed)
    df = pd.DataFrame(x, columns=[f"f{i}" for i in range(x.shape[1])])
    df["label"] = y
    return df


if __name__ == "__main__":
    out = Path(__file__).parent / "fixtures"
    out.mkdir(exist_ok=True)
    for name, (seed, noise) in FIXTURES.items():
        make_fixture(seed, noise).to_csv(out / f"{name}.csv", index=False)
        print(f"wrote fixtures/{name}.csv")
