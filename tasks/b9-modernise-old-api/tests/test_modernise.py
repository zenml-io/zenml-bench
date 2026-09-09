"""Grader for B9 modernise-old-api. Runs the entrypoint on the image's data and on an unseen fixture.

Before each run, every existing step run is expired as a cache candidate (documented ZenML API), so the
agent's own earlier runs cannot serve cached artifacts and the score must come from a real execution.
Env: APP_DIR (default /app/legacy_training), FIXTURES_DIR (default /tests/fixtures).
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from zenml.client import Client
from zenml.enums import ExecutionStatus

APP_DIR = Path(os.environ.get("APP_DIR", "/app/legacy_training"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
PIPELINE = "training_pipeline"
STEPS = {"load_data", "split", "train", "evaluate"}
OUTPUTS = {"load_data": {"features", "labels"}, "split": {"x_train", "x_test", "y_train", "y_test"}, "evaluate": {"score"}}
PARAMS = {"split": {"test_size": 0.25, "seed": 0}, "train": {"C": 0.5}}
TOL = 1e-4


def expire_all_step_runs() -> None:
    c = Client()
    for run in c.list_pipeline_runs(size=500).items:
        for step in run.steps.values():
            c.update_step_run(step.id, cache_expires_at=datetime.now(timezone.utc))


def run_entrypoint() -> tuple[Any, str]:
    expire_all_step_runs()
    seen = {r.id for r in Client().list_pipeline_runs(size=500).items}
    proc = subprocess.run([sys.executable, "run.py"], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"entrypoint failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
    new = [r for r in Client().list_pipeline_runs(sort_by="desc:created", size=5).items if r.id not in seen]
    assert len(new) == 1, f"expected exactly one new pipeline run, found {len(new)}"
    return new[0], proc.stdout


def flat_values(obj: Any) -> list[Any]:
    """All leaf values of a nested dict/list, so parameters can be checked whether flat or nested in a model."""
    if isinstance(obj, dict):
        return [v for x in obj.values() for v in flat_values(x)]
    if isinstance(obj, list):
        return [v for x in obj for v in flat_values(x)]
    return [obj]


def printed_score(stdout: str) -> float:
    m = re.search(r"^score:\s*([0-9.eE+-]+)\s*$", stdout, re.M)
    assert m, f"no 'score: <value>' line in stdout:\n{stdout[-1000:]}"
    return float(m.group(1))


@pytest.fixture(scope="module")
def expected() -> dict[str, float]:
    return json.loads((FIXTURES / "expected.json").read_text())


@pytest.fixture(scope="module")
def run_a() -> tuple[Any, str]:
    shutil.copy(FIXTURES / "a.csv", APP_DIR / "data" / "train.csv")
    return run_entrypoint()


@pytest.fixture(scope="module")
def run_c(run_a) -> tuple[Any, str]:
    shutil.copy(FIXTURES / "c.csv", APP_DIR / "data" / "train.csv")
    return run_entrypoint()


def test_run_completed_with_same_step_graph(run_a):
    run, _ = run_a
    assert run.status == ExecutionStatus.COMPLETED
    assert run.pipeline.name == PIPELINE
    assert set(run.steps) == STEPS, f"steps were {set(run.steps)}"
    assert all(s.status in (ExecutionStatus.COMPLETED, ExecutionStatus.CACHED) for s in run.steps.values())


def test_output_names_preserved(run_a):
    run, _ = run_a
    for step, names in OUTPUTS.items():
        assert set(run.steps[step].outputs) == names, f"{step} outputs were {set(run.steps[step].outputs)}"
    assert len(run.steps["train"].outputs) == 1


def test_parameters_recorded(run_a):
    run, _ = run_a
    for step, wanted in PARAMS.items():
        recorded = flat_values(run.steps[step].config.parameters)
        for key, value in wanted.items():
            assert value in recorded, f"{step}.{key}={value} not among recorded parameters {run.steps[step].config.parameters}"


def test_score_on_image_data(run_a, expected):
    run, stdout = run_a
    stored = float(run.steps["evaluate"].outputs["score"][0].load())
    assert stored == pytest.approx(expected["a"], abs=TOL)
    assert printed_score(stdout) == pytest.approx(stored, abs=TOL)


def test_score_on_unseen_data(run_c, expected):
    run, stdout = run_c
    stored = float(run.steps["evaluate"].outputs["score"][0].load())
    assert stored == pytest.approx(expected["c"], abs=TOL)
    assert printed_score(stdout) == pytest.approx(stored, abs=TOL)


def test_collateral():
    assert {p.name for p in Client().list_pipelines(size=50).items} == {PIPELINE}
