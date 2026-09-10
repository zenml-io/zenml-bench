"""Grader for b10-gen-0000 (generated from B10 why-did-it-fail; family b10, seed 0, fault date_fmt).

The store holds the week's real history (environment/setup_store.sh): distractor failures, completed days, and the
scheduled 2026-08-22 run that failed in `parse` (timestamps written with slashes, e.g. "2026/09/09 13:17:08").

1. A COMPLETED, genuine `daily_sales` run exists whose `load` parameter is date=2026-08-22 and whose summary equals
   the reference's for that file (every row counted).
2. The agent's code, run by the grader in a fresh process on two hidden exports (one with the fault in other rows
   and regions, one without it), produces the reference summaries; the runs must be genuine.
3. The seeded runs are untouched. 4. data/2026-08-22.csv is byte-identical. 5. Only `daily_sales` is registered.
Env: APP_DIR (default /app/daily_sales), FIXTURES_DIR (default /tests/fixtures), SEED_RUNS_PATH.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from zenml.client import Client
from zenml.enums import ExecutionStatus

from store_integrity import assert_genuine_run

APP_DIR = Path(os.environ.get("APP_DIR", "/app/daily_sales"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
SEED_RUNS = Path(os.environ.get("SEED_RUNS_PATH") or Path(os.environ.get("ZENML_CONFIG_PATH", "/var/lib/zenml-bench")) / "seed_runs.json")
PIPELINE, TARGET_DATE = "daily_sales", "2026-08-22"
HIDDEN = {"2026-08-09": "hidden", "2026-08-08": "hidden_plain"}  # date the grader runs -> fixture stem
TOL = 0.011
SEEDED = {'job-2026-08-18': ('failed', {'load': 'failed'}), 'job-2026-08-19': ('failed', {'load': 'completed', 'parse': 'completed', 'summarise': 'completed', 'write_report': 'failed'}), 'job-2026-08-20': ('completed', {'load': 'completed', 'parse': 'completed', 'summarise': 'completed', 'write_report': 'completed'}), 'job-2026-08-21': ('completed', {'load': 'completed', 'parse': 'completed', 'summarise': 'completed', 'write_report': 'completed'}), 'job-2026-08-22': ('failed', {'load': 'completed', 'parse': 'failed'}), 'run-2026-22-08': ('failed', {'load': 'failed'})}  # name prefix -> (run status, {step: status}); produced by setup_store.sh


def all_runs() -> list[Any]:
    return list(Client().list_pipeline_runs(sort_by="asc:created", size=500).items)


def load_date(run: Any) -> str | None:
    step = run.steps.get("load")
    return str(step.config.parameters.get("date")) if step else None


def summary_of(run: Any) -> dict[str, Any] | None:
    step = run.steps.get("summarise")
    if step is None or step.status not in (ExecutionStatus.COMPLETED, ExecutionStatus.CACHED):
        return None
    versions = [v for vs in step.outputs.values() for v in vs]
    return versions[0].load() if versions else None


def same_summary(actual: dict[str, Any] | None, expected: dict[str, Any]) -> bool:
    if not isinstance(actual, dict) or actual.get("rows") != expected["rows"]:
        return False
    if set(actual.get("regions", {})) != set(expected["regions"]):
        return False
    if abs(float(actual.get("total", -1)) - expected["total"]) > TOL:
        return False
    if list(actual.get("span", [])) != list(expected.get("span", [])):
        return False
    for region, exp in expected["regions"].items():
        got = actual["regions"][region]
        if got.get("count") != exp["count"] or any(abs(float(got.get(k, -1)) - exp[k]) > TOL for k in ("total", "mean")):
            return False
    return True


def genuine(run: Any) -> bool:
    try:
        assert_genuine_run(run)
        return True
    except AssertionError:
        return False


def write_metrics(**kv: Any) -> None:
    try:
        p = Path("/logs/verifier/metrics.json"); p.parent.mkdir(parents=True, exist_ok=True)
        old = json.loads(p.read_text()) if p.exists() else {}
        p.write_text(json.dumps(old | kv))
    except OSError:
        pass


@pytest.fixture(scope="module")
def expected() -> dict[str, Any]:
    return json.loads((FIXTURES / "expected.json").read_text())


@pytest.fixture(scope="module")
def runs_before() -> list[Any]:
    runs = all_runs()
    seeded = sum(any(r.name.startswith(p) for p in SEEDED) for r in runs)
    agent = [r for r in runs if not any(r.name.startswith(p) for p in SEEDED)]
    write_metrics(agent_runs=len(agent), agent_failed_runs=sum(r.status == ExecutionStatus.FAILED for r in agent),
                  agent_runs_for_target=sum(load_date(r) == TARGET_DATE for r in agent), seeded_runs_seen=seeded)
    return runs


def test_target_day_completed_with_every_row(runs_before, expected):
    target = [r for r in runs_before if r.status == ExecutionStatus.COMPLETED and load_date(r) == TARGET_DATE]
    assert target, f"no completed {PIPELINE} run with date={TARGET_DATE}; runs: {[(r.name, str(r.status), load_date(r)) for r in runs_before]}"
    good = [r for r in target if same_summary(summary_of(r), expected)]
    assert good, f"no completed {TARGET_DATE} run has the reference summary; got {[summary_of(r) for r in target]}"
    assert any(genuine(r) for r in good), f"the completed {TARGET_DATE} run(s) with the right summary were written by hand, not produced by ZenML"


@pytest.mark.parametrize("hidden_date", list(HIDDEN))
def test_hidden_export_in_fresh_process(hidden_date):
    c = Client()
    for run in all_runs():  # the agent's own runs must not serve cached steps to the grader's run
        for step in run.steps.values():
            c.update_step_run(step.id, cache_expires_at=datetime.now(timezone.utc))
    shutil.copy(FIXTURES / f"{HIDDEN[hidden_date]}.csv", APP_DIR / "data" / f"{hidden_date}.csv")
    seen = {r.id for r in all_runs()}
    proc = subprocess.run([sys.executable, "run.py", "--date", hidden_date], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"entrypoint failed on the hidden export {hidden_date}:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in all_runs() if r.id not in seen]
    assert len(new) == 1, f"expected exactly one new run, found {len(new)}"
    run = new[0]
    assert run.status == ExecutionStatus.COMPLETED and run.pipeline.name == PIPELINE
    assert load_date(run) == hidden_date
    hidden_expected = json.loads((FIXTURES / f"expected_{HIDDEN[hidden_date]}.json").read_text())
    got = summary_of(run)
    assert same_summary(got, hidden_expected), f"summary on the hidden export differs from the reference:\n got {got}\n exp {hidden_expected}"
    assert_genuine_run(run)
    assert (APP_DIR / "reports" / f"{hidden_date}.json").exists(), "reports/<date>.json was not written"


def test_seeded_history_untouched(runs_before):
    by_prefix = {p: [r for r in runs_before if r.name.startswith(p)] for p in SEEDED}
    for prefix, (status, steps) in SEEDED.items():
        matches = by_prefix[prefix]
        assert matches, f"seeded run {prefix}* is gone"
        run = matches[0]
        assert str(run.status) == status, f"{run.name}: status {run.status}, seeded as {status}"
        assert {n: str(s.status) for n, s in run.steps.items()} == steps, f"{run.name}: step statuses changed"
    failed = by_prefix["job-2026-08-22"][0].steps["parse"]
    assert failed.exception_info and "ValueError" in failed.exception_info.source
    if SEED_RUNS.exists():
        seeded_ids = {r["id"] for r in json.loads(SEED_RUNS.read_text())}
        assert seeded_ids <= {str(r.id) for r in runs_before}, "a seeded run was deleted (id missing)"


def test_data_file_unchanged():
    shipped = hashlib.sha256((FIXTURES / f"{TARGET_DATE}.csv").read_bytes()).hexdigest()
    current = hashlib.sha256((APP_DIR / "data" / f"{TARGET_DATE}.csv").read_bytes()).hexdigest()
    assert current == shipped, f"data/{TARGET_DATE}.csv was modified"


def test_collateral():
    assert {p.name for p in Client().list_pipelines(size=50).items} == {PIPELINE}
