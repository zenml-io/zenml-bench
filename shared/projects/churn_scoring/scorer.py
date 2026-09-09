"""ChurnScorer: the object the training pipeline produces and the serving script loads."""
import sqlite3
from typing import Sequence

import pandas as pd
from sklearn.linear_model import LogisticRegression

SEGMENT_BOOST = {0: 0.0, 1: 0.05, 2: -0.05}  # per-segment calibration, looked up through SQLite at score time


class ChurnScorer:
    """A fitted model plus the feature order, a decision threshold, and a segment lookup table.

    The lookup table is an in-memory SQLite database so segment rules can be queried with SQL.
    """

    def __init__(self, model: LogisticRegression, features: Sequence[str], threshold: float) -> None:
        self.model = model
        self.features = list(features)
        self.threshold = threshold
        self.lookup = sqlite3.connect(":memory:")
        self.lookup.execute("CREATE TABLE segment_boost (segment INTEGER PRIMARY KEY, boost REAL)")
        self.lookup.executemany("INSERT INTO segment_boost VALUES (?, ?)", SEGMENT_BOOST.items())

    def boost_for(self, segment: int) -> float:
        row = self.lookup.execute("SELECT boost FROM segment_boost WHERE segment = ?", (segment,)).fetchone()
        return float(row[0]) if row else 0.0

    def score(self, df: pd.DataFrame) -> list[float]:
        """Churn probability per row, calibrated by segment (segment = row index modulo 3)."""
        probs = self.model.predict_proba(df[self.features])[:, 1]
        return [float(min(1.0, max(0.0, p + self.boost_for(i % 3)))) for i, p in enumerate(probs)]

    def flag(self, df: pd.DataFrame) -> list[bool]:
        return [s >= self.threshold for s in self.score(df)]
