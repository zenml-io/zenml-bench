"""Grader for B2 script-to-pipeline. Runs the agent's entrypoint on the visible data and on a hidden file, and
compares the recorded `accuracy` artifact with what the ORIGINAL script (tests/reference_train.py, a copy of the
pre-task train.py) prints for the same file. Structure is read from the run: the `accuracy` artifact's producer
step must take the `model` artifact as an input, and the model step must take an artifact another step produced.
Env: APP_DIR (default /app/credit_script), FIXTURES_DIR (default /tests/fixtures).
"""
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from zenml.client import Client
from zenml.enums import ExecutionStatus

APP_DIR = Path(os.environ.get("APP_DIR", "/app/credit_script"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
REFERENCE = Path(__file__).with_name("reference_train.py")
PIPELINE = "credit_training"
DATASETS = {"visible": APP_DIR / "data" / "credit.csv", "hidden": FIXTURES / "hidden.csv"}
TOL = 1e-6


def run_entrypoint(data: Path) -> Any:
    seen = {r.id for r in Client().list_pipeline_runs(size=500).items}
    proc = subprocess.run([sys.executable, "train.py", "--data", str(data)], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"entrypoint failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in Client().list_pipeline_runs(sort_by="desc:created", size=5).items if r.id not in seen]
    assert len(new) == 1, f"expected exactly one new run, found {len(new)}"
    return new[0]


def reference_accuracy(data: Path) -> float:
    proc = subprocess.run([sys.executable, str(REFERENCE), "--data", str(data)], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-1000:]
    return float(re.search(r"accuracy=([0-9.]+)", proc.stdout).group(1))


def outputs_named(run: Any, name: str) -> list[tuple[str, Any]]:
    return [(step_name, v) for step_name, st in run.steps.items() for vs in st.outputs.values() for v in vs if v.artifact.name == name]


@pytest.fixture(scope="module")
def runs() -> dict[str, Any]:
    return {k: run_entrypoint(p) for k, p in DATASETS.items()}


def test_runs_completed(runs):
    for r in runs.values():
        assert r.status == ExecutionStatus.COMPLETED
        assert r.pipeline.name == PIPELINE, f"pipeline is {r.pipeline.name}"
        assert len(r.steps) >= 3, f"only {len(r.steps)} steps: {list(r.steps)}"


def test_model_and_accuracy_are_tracked_artifacts(runs):
    for label, r in runs.items():
        models, accs = outputs_named(r, "model"), outputs_named(r, "accuracy")
        assert len(models) == 1, f"{label}: expected one output named 'model', found {len(models)}"
        assert len(accs) == 1, f"{label}: expected one output named 'accuracy', found {len(accs)}"
        model = models[0][1].load()
        assert hasattr(model, "predict") and type(model).__module__.startswith("sklearn"), f"{label}: model artifact is {type(model)}"
        assert accs[0][1].data_type.import_path == "builtins.float", f"{label}: accuracy artifact type is {accs[0][1].data_type.import_path}"


def test_steps_are_separate_and_wired(runs):
    r = runs["hidden"]
    (model_step, model_av), = outputs_named(r, "model")
    (acc_step, _), = outputs_named(r, "accuracy")
    assert model_step != acc_step, "model and accuracy come from the same step (training and evaluation are not separate steps)"
    eval_inputs = {v.id for vs in r.steps[acc_step].inputs.values() for v in vs}
    assert model_av.id in eval_inputs, f"step {acc_step!r} does not take the model artifact as an input"
    produced_by_others = {v.id for name, st in r.steps.items() if name != model_step for vs in st.outputs.values() for v in vs}
    train_inputs = {v.id for vs in r.steps[model_step].inputs.values() for v in vs}
    assert train_inputs & produced_by_others, f"step {model_step!r} takes no artifact produced by a preparation step"


def test_accuracy_matches_the_script(runs):
    for label, r in runs.items():
        (_, av), = outputs_named(r, "accuracy")
        recorded, expected = float(av.load()), reference_accuracy(DATASETS[label])
        assert recorded == pytest.approx(expected, abs=TOL), f"{label}: recorded accuracy {recorded} != script's {expected}"


def test_collateral():
    assert {p.name for p in Client().list_pipelines(size=50).items} == {PIPELINE}
