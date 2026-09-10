"""Legacy monthly report. Run from this directory: `python report.py`."""
from typing import Annotated

from zenml import pipeline, step


@step
def count_rows() -> Annotated[int, "rows"]:
    return 42


@step
def render(rows: int) -> Annotated[str, "report"]:
    return f"monthly report: {rows} rows"


@pipeline
def legacy_report() -> None:
    render(rows=count_rows())


if __name__ == "__main__":
    legacy_report()
