"""Grader for B10 why-did-it-fail.

The store holds the week's real history (environment/setup_store.sh): a run that failed because a file was
missing, one that failed because reports/ was missing (since fixed), two that completed, the scheduled
2026-09-09 run that failed in `parse` on amounts like "1,234.50", and a later manual run with a typo'd date.

1. A COMPLETED `daily_report` run exists whose `load` parameter is date=2026-09-09 and whose summary equals the
   reference's for that file (every row counted, separator amounts parsed).
2. The agent's code, run by the grader in a fresh process on a hidden export with separator amounts in other
   rows and regions, produces the reference summary. Symptom patches (drop rows, NaN, editing the CSV, fixing
   a distractor) fail here or in 1.
3. The seeded runs are untouched: same names, ids (when the manifest is present), statuses and failed steps.
4. data/2026-09-09.csv is byte-identical to the shipped file.
5. No pipeline other than `daily_report` is registered.
Env: APP_DIR (default /app/daily_report), FIXTURES_DIR (default /tests/fixtures), SEED_RUNS_PATH (default:
$ZENML_CONFIG_PATH/seed_runs.json, else /var/lib/zenml-bench/seed_runs.json).
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

APP_DIR = Path(os.environ.get("APP_DIR", "/app/daily_report"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
SEED_RUNS = Path(os.environ.get("SEED_RUNS_PATH") or Path(os.environ.get("ZENML_CONFIG_PATH", "/var/lib/zenml-bench")) / "seed_runs.json")
PIPELINE, TARGET_DATE = "daily_report", "2026-09-09"
HIDDEN = {"2026-08-31": "hidden", "2026-08-30": "hidden_plain"}  # date the grader runs -> fixture stem
TOL = 0.011  # summaries are rounded to 2 dp; allow one unit in the last place either way
SEEDED = {  # name prefix -> (run status, {step: status}); produced by setup_store.sh
    "scheduled-2026-09-05": ("failed", {"load": "failed"}),
    "scheduled-2026-09-06": ("failed", {"load": "completed", "parse": "completed", "summarise": "completed", "write_report": "failed"}),
    "scheduled-2026-09-07": ("completed", {"load": "completed", "parse": "completed", "summarise": "completed", "write_report": "completed"}),
    "scheduled-2026-09-08": ("completed", {"load": "completed", "parse": "completed", "summarise": "completed", "write_report": "completed"}),
    "scheduled-2026-09-09": ("failed", {"load": "completed", "parse": "failed"}),
    "manual-2026-09-31": ("failed", {"load": "failed"}),
}


def all_runs() -> list[Any]:
    return list(Client().list_pipeline_runs(sort_by="asc:created", size=500).items)


def load_date(run: Any) -> str | None:
    step = run.steps.get("load")
    return str(step.config.parameters.get("date")) if step else None


def summary_of(run: Any) -> dict[str, Any] | None:
    step = run.steps.get("summarise")
    if step is None or step.status != ExecutionStatus.COMPLETED and step.status != ExecutionStatus.CACHED:
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
    for region, exp in expected["regions"].items():
        got = actual["regions"][region]
        if got.get("count") != exp["count"] or any(abs(float(got.get(k, -1)) - exp[k]) > TOL for k in ("total", "mean")):
            return False
    return True


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
    """Check 1: a completed run processed 2026-09-09 and its summary matches the reference."""
    target = [r for r in runs_before if r.status == ExecutionStatus.COMPLETED and load_date(r) == TARGET_DATE]
    assert target, f"no completed {PIPELINE} run with date={TARGET_DATE}; runs: {[(r.name, str(r.status), load_date(r)) for r in runs_before]}"
    summaries = [summary_of(r) for r in target]
    assert any(same_summary(s, expected) for s in summaries), f"no completed {TARGET_DATE} run has the reference summary; got {summaries}"


@pytest.mark.parametrize("hidden_date", list(HIDDEN))
def test_hidden_export_in_fresh_process(hidden_date):
    """Check 2: the grader runs the agent's entrypoint on exports it never saw: one with separator amounts in
    other rows and regions, one without any (a fix must not break the normal day)."""
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
    assert (APP_DIR / "reports" / f"{hidden_date}.json").exists(), "reports/<date>.json was not written"


def test_seeded_history_untouched(runs_before):
    """Check 3: the original runs still exist with their statuses and failed steps."""
    by_prefix = {p: [r for r in runs_before if r.name.startswith(p)] for p in SEEDED}
    for prefix, (status, steps) in SEEDED.items():
        matches = by_prefix[prefix]
        assert matches, f"seeded run {prefix}* is gone"
        run = matches[0]
        assert str(run.status) == status, f"{run.name}: status {run.status}, seeded as {status}"
        assert {n: str(s.status) for n, s in run.steps.items()} == steps, f"{run.name}: step statuses changed"
    parse = by_prefix["scheduled-2026-09-09"][0].steps["parse"]
    assert parse.exception_info and "ValueError" in parse.exception_info.source
    if SEED_RUNS.exists():
        seeded_ids = {r["id"] for r in json.loads(SEED_RUNS.read_text())}
        assert seeded_ids <= {str(r.id) for r in runs_before}, "a seeded run was deleted (id missing)"


def test_data_file_unchanged():
    """Check 4: the fix must be in the code, not in the export."""
    shipped = hashlib.sha256((FIXTURES / f"{TARGET_DATE}.csv").read_bytes()).hexdigest()
    current = hashlib.sha256((APP_DIR / "data" / f"{TARGET_DATE}.csv").read_bytes()).hexdigest()
    assert current == shipped, f"data/{TARGET_DATE}.csv was modified"


def test_collateral():
    """Check 5: no stray pipelines."""
    assert {p.name for p in Client().list_pipelines(size=50).items} == {PIPELINE}
