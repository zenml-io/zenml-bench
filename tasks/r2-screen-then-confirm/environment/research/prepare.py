"""Data, evaluation and screening seeds for the research loop. READ-ONLY: the grader uses its own copy.

- load_data() -> (X_train, y_train, X_val, y_val): a binary classification problem, 20 features.
- subsample(X, y, seed): the training slice a run may use. Each seed draws a different 35% of the rows, so the
  same config scores differently from seed to seed. That noise is deliberate: it is what you must reason about.
- evaluate(model, X, y) -> float: validation log loss (lower is better) from model.predict_proba.
- SCREENING_SEEDS: the seeds you may use for screening. The grader evaluates on data you cannot see.
"""
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import log_loss

DATA_DIR = Path(__file__).parent / "data"
SCREENING_SEEDS: list[int] = [0, 1, 2, 3, 4]
SUBSAMPLE_FRACTION = 0.35


def load_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    train, val = np.load(DATA_DIR / "train.npz"), np.load(DATA_DIR / "val.npz")
    return train["X"], train["y"], val["X"], val["y"]


def subsample(X: np.ndarray, y: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """The training rows a run with this seed may use: a seed-specific 35% slice, no replacement."""
    idx = np.random.default_rng(seed).choice(len(X), size=int(len(X) * SUBSAMPLE_FRACTION), replace=False)
    return X[idx], y[idx]


def evaluate(model: Any, X: np.ndarray, y: np.ndarray) -> float:
    """Validation log loss (lower is better). The model must implement predict_proba."""
    return float(log_loss(y, model.predict_proba(X)[:, 1], labels=[0, 1]))
