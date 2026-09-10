"""Smoke-check pipeline for the fraud-scoring team. Runs on whatever ZenML stack is active: `python run.py`."""
from typing import Annotated

from zenml import pipeline, step


@step
def make_scores(n: int = 20) -> Annotated[list[float], "scores"]:
    return [round(i / n, 3) for i in range(n)]


@step
def flag_rate(scores: list[float], threshold: float = 0.8) -> Annotated[float, "flag_rate"]:
    rate = sum(s >= threshold for s in scores) / len(scores)
    print(f"flag_rate={rate:.3f}")
    return rate


@pipeline
def smoke_check(n: int = 20, threshold: float = 0.8) -> None:
    flag_rate(scores=make_scores(n=n), threshold=threshold)


if __name__ == "__main__":
    smoke_check()
