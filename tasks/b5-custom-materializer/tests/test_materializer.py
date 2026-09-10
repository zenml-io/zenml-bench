"""Grader for B5 custom-materializer.

1. `python run.py` completes; an artifact version named `churn_scorer` exists and was produced by that run.
2. In a fresh interpreter (tests/load_and_score.py, cwd = project), the artifact loads by name and scores a hidden
   fixture; scores must match the reference's within tolerance. This is behaviour-based: any persistence
   mechanism that round-trips the scorer's behaviour passes.
3. Metric (not graded): which materializer the store recorded, written to /logs/verifier/metrics.json.
Env: APP_DIR (default /app/churn_scoring), FIXTURES_DIR (default /tests/fixtures).
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from zenml.client import Client
from zenml.enums import ExecutionStatus

from store_integrity import assert_genuine_run

APP_DIR = Path(os.environ.get("APP_DIR", "/app/churn_scoring"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
LOADER = Path(__file__).with_name("load_and_score.py")
PIPELINE, ARTIFACT = "churn_training", "churn_scorer"
TOL = 1e-6


def fresh(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=APP_DIR, capture_output=True, text=True, timeout=600)


@pytest.fixture(scope="module")
def run() -> Any:
    seen = {r.id for r in Client().list_pipeline_runs(size=500).items}
    proc = fresh([sys.executable, "run.py"])
    assert proc.returncode == 0, f"entrypoint failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in Client().list_pipeline_runs(sort_by="desc:created", size=5).items if r.id not in seen]
    assert len(new) == 1
    return new[0]


@pytest.fixture(scope="module")
def artifact(run) -> Any:
    av = Client().get_artifact_version(ARTIFACT)
    try:
        Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
        custom = "cloudpickle" not in str(av.materializer)
        Path("/logs/verifier/metrics.json").write_text(json.dumps({"used_custom_materializer": int(custom)}))
    except OSError:
        pass
    return av


def test_run_completed(run):
    assert run.status == ExecutionStatus.COMPLETED
    assert run.pipeline.name == PIPELINE
    assert "flag_rate" in run.steps["evaluate"].outputs


def test_train_output_is_named_churn_scorer(run, artifact):
    """The graded run's `train` step must produce a version of the artifact named `churn_scorer`. The step may be
    CACHED (the agent ran the pipeline before grading) and the cached version need not be the *latest* one: an
    agent's later debug run may have produced a newer version. Behaviour of the latest version is checked below."""
    outputs = [v for versions in run.steps["train"].outputs.values() for v in versions]
    assert ARTIFACT in {v.artifact.name for v in outputs}, f"train outputs are named {[v.artifact.name for v in outputs]}"
    assert artifact.artifact.name == ARTIFACT


def test_loads_and_scores_in_fresh_process(artifact):
    proc = fresh([sys.executable, str(LOADER), str(FIXTURES / "hidden.csv")])
    assert proc.returncode == 0, f"fresh-process load failed:\n{proc.stdout[-800:]}\n{proc.stderr[-1500:]}"
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    expected = json.loads((FIXTURES / "expected_hidden.json").read_text())
    assert out["type"].endswith("ChurnScorer"), f"loaded object is {out['type']}"
    assert out["scores"] == pytest.approx(expected, abs=TOL), "scores on hidden data differ from the reference scorer"


def test_run_is_genuine(run):
    """Defeats tests/shortcuts/tamper_store.sh: a hand-saved artifact named `churn_scorer` attached to `train` after the run."""
    assert_genuine_run(run)


def test_collateral():
    assert {p.name for p in Client().list_pipelines(size=50).items} == {PIPELINE}
