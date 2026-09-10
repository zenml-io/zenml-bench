"""Grader for B4 nondeterministic-step. Runs the entrypoint twice with an `n` the agent has not used and reads the store.

Observed at 0.96.4 (docs/decisions.md 2026-09-10): with the fault, run 2 has every step CACHED and the same
`review_sample` artifact version; with a working fix `load_events` is CACHED and `sample_events` COMPLETED on run 2
with a different sample. Run 1's `sample_events` is a fresh cache key whatever the fix (new `n`), so nothing is
asserted about run 1's statuses except completion. The agent may have run the pipeline before, so `load_events`
may be CACHED on run 1 too; that is fine and expected.
Env: APP_DIR (default /app/sampling), FIXTURES_DIR (default /tests/fixtures).
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from zenml.client import Client
from zenml.enums import ExecutionStatus

from store_integrity import assert_genuine_run

APP_DIR = Path(os.environ.get("APP_DIR", "/app/sampling"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
PIPELINE, STEPS = "qa_sampling", ["load_events", "sample_events", "review_report"]
N = int(json.loads((FIXTURES / "expected.json").read_text())["n"])


def run_entrypoint(n: int) -> Any:
    seen = {r.id for r in Client().list_pipeline_runs(size=500).items}
    proc = subprocess.run([sys.executable, "run.py", "--n", str(n)], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"entrypoint failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in Client().list_pipeline_runs(sort_by="desc:created", size=5).items if r.id not in seen]
    assert len(new) == 1, f"expected exactly one new run, found {len(new)}"
    return new[0]


def sample_ids(run: Any) -> list[int]:
    df = run.steps["sample_events"].outputs["review_sample"][0].load()
    return sorted(int(i) for i in df["event_id"])


def report(run: Any) -> dict[str, Any]:
    return run.steps["review_report"].outputs["review_report"][0].load()


@pytest.fixture(scope="module")
def runs() -> list[Any]:
    return [run_entrypoint(N), run_entrypoint(N)]


@pytest.fixture(scope="module")
def valid_ids() -> set[int]:
    df = pd.read_csv(APP_DIR / "data" / "events.csv")
    return set(int(i) for i in df.loc[df["amount"] > 0, "event_id"])


def test_runs_completed(runs):
    for r in runs:
        assert r.status == ExecutionStatus.COMPLETED
        assert r.pipeline.name == PIPELINE
        assert list(r.steps) == STEPS, f"steps are {list(r.steps)}"


def test_loader_cached_on_second_run(runs):
    assert runs[1].steps["load_events"].status == ExecutionStatus.CACHED, "load_events was re-executed on an unchanged run (caching disabled too broadly)"


def test_sampler_executes_on_second_run(runs):
    assert runs[1].steps["sample_events"].status == ExecutionStatus.COMPLETED, f"sample_events was {runs[1].steps['sample_events'].status.value} on the second run"


def test_samples_are_fresh_and_real(runs, valid_ids):
    a, b = sample_ids(runs[0]), sample_ids(runs[1])
    assert len(a) == N and len(b) == N, f"sample sizes {len(a)}, {len(b)} (asked for {N})"
    assert len(set(a)) == N and set(a) <= valid_ids, "run 1 sample is not a set of real event ids"
    assert len(set(b)) == N and set(b) <= valid_ids, "run 2 sample is not a set of real event ids"
    assert a != b, "both runs drew the same sample"


def test_report_matches_its_own_run(runs):
    for r in runs:
        rep = report(r)
        assert rep["n"] == N
        assert sorted(rep["event_ids"]) == sample_ids(r), "review_report does not describe the sample drawn in the same run"
        df = r.steps["sample_events"].outputs["review_sample"][0].load()
        assert rep["total_amount"] == pytest.approx(round(float(df["amount"].sum()), 2), abs=1e-2)


def test_runs_are_genuine(runs):
    """Defeats tests/shortcuts/tamper_store.sh (status flipped to "cached" in SQLite after a real execution)."""
    for r in runs:
        assert_genuine_run(r)


def test_collateral():
    assert {p.name for p in Client().list_pipelines(size=50).items} == {PIPELINE}
