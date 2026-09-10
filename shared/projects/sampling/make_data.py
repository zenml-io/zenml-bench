# /// script
# requires-python = ">=3.14"
# dependencies = ["pandas", "numpy"]
# ///
"""Regenerates data/events.csv (the project's event log). Run from this directory: `uv run make_data.py`."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(2026)
n = 20_000
df = pd.DataFrame({
    "event_id": np.arange(1, n + 1),
    "user_id": rng.integers(1, 4000, n),
    "amount": np.round(rng.gamma(2.0, 45.0, n), 2),
    "channel": rng.choice(["web", "app", "pos"], n, p=[0.5, 0.35, 0.15]),
})
df.to_csv("data/events.csv", index=False)
print(df.describe())
