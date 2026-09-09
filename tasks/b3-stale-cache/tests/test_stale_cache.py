"""Grader for B3 stale-cache. Runs the agent's entrypoint against fresh fixtures and reads the store.

Sequence: a, a, b, b, c. Assertions come from observed ZenML 0.96.4 behaviour (docs/decisions.md).
Env: APP_DIR (default /app/nightly), FIXTURES_DIR (default /tests/fixtures).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from zenml.client import Client
from zenml.enums import ExecutionStatus

APP_DIR = Path(os.environ.get("APP_DIR", "/app/nightly"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
PIPELINE = "nightly_training"
TOL = 1e-4
SEQUENCE = ["a", "a", "b", "b", "c"]


def run_entrypoint() -> Any:
    """Run `python run.py` in the project and return the run it created."""
    seen = {r.id for r in Client().list_pipeline_runs(size=200).items}
    proc = subprocess.run([sys.executable, "run.py"], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"entrypoint failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
    new = [r for r in Client().list_pipeline_runs(sort_by="desc:created", size=5).items if r.id not in seen]
    assert len(new) == 1, f"expected exactly one new run, found {len(new)}"
    return new[0]


def score_of(run: Any) -> float:
    return float(run.steps["evaluate"].outputs["score"][0].load())


def status(run: Any, step: str) -> ExecutionStatus:
    return run.steps[step].status


@pytest.fixture(scope="module")
def runs() -> list[Any]:
    out = []
    for name in SEQUENCE:
        shutil.copy(FIXTURES / f"{name}.csv", APP_DIR / "data" / "train.csv")
        out.append(run_entrypoint())
    return out


@pytest.fixture(scope="module")
def expected() -> dict[str, float]:
    return json.loads((FIXTURES / "expected.json").read_text())


def test_all_runs_completed(runs):
    assert [r.status for r in runs] == [ExecutionStatus.COMPLETED] * len(SEQUENCE)
    assert all(r.pipeline.name == PIPELINE for r in runs)


def test_scores_track_the_data(runs, expected):
    got = [score_of(r) for r in runs]
    want = [expected[n] for n in SEQUENCE]
    assert got == pytest.approx(want, abs=TOL), f"scores {got} != expected {want}"


def test_train_reruns_when_data_changes(runs):
    assert status(runs[0], "train") == ExecutionStatus.COMPLETED
    assert status(runs[2], "train") == ExecutionStatus.COMPLETED  # a -> b
    assert status(runs[4], "train") == ExecutionStatus.COMPLETED  # b -> c


def test_train_is_cached_on_unchanged_rerun(runs):
    assert status(runs[1], "train") == ExecutionStatus.CACHED  # a again
    assert status(runs[3], "train") == ExecutionStatus.CACHED  # b again


def test_collateral(runs):
    names = {p.name for p in Client().list_pipelines(size=50).items}
    assert names == {PIPELINE}, f"unexpected pipelines registered: {names}"
    assert "score" in runs[-1].steps["evaluate"].outputs
