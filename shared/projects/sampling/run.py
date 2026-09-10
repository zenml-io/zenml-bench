"""Daily QA sampling pipeline: draw a fresh random sample of events for manual review.

Run from this directory: `python run.py [--n 50]`.
"""
import argparse
import time
from typing import Annotated

import pandas as pd
from zenml import pipeline, step

DATA_PATH = "data/events.csv"


@step
def load_events() -> pd.DataFrame:
    """Expensive: in production this is a warehouse query that takes minutes. Cache it."""
    time.sleep(3)
    df = pd.read_csv(DATA_PATH)
    return df[df["amount"] > 0].reset_index(drop=True)


@step
def sample_events(events: pd.DataFrame, n: int) -> Annotated[pd.DataFrame, "review_sample"]:
    """A fresh random sample every run: reviewers must not see the same rows twice."""
    return events.sample(n=n).reset_index(drop=True)


@step
def review_report(sample: pd.DataFrame) -> Annotated[dict, "review_report"]:
    report = {
        "n": int(len(sample)),
        "event_ids": sorted(int(i) for i in sample["event_id"]),
        "total_amount": round(float(sample["amount"].sum()), 2),
    }
    print(f"sampled {report['n']} events, total amount {report['total_amount']}")
    return report


@pipeline
def qa_sampling(n: int = 50) -> None:
    review_report(sample=sample_events(events=load_events(), n=n))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    qa_sampling(n=ap.parse_args().n)
