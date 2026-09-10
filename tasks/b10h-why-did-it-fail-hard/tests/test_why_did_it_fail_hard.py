"""Grader for B10H why-did-it-fail (hard).

The store holds the week's real history (environment/setup_store.sh). Two scheduled runs failed on data faults
whose exports were then quarantined off the box: 2026-09-03 (region names "North" / "west " -> ValueError in
`summarise`) and 2026-09-09, this morning (amounts "1,234.50" -> ValueError in `parse`). The other failures
(no export on 09-05, reports/ removed on 09-06, a hand re-run of an old ISO-timestamp export, a typo'd date)
are not code faults. The instruction names neither the day, the cause, nor how scheduled runs are recorded.

1. No export was fabricated for a quarantined day (data/2026-09-09.csv, data/2026-09-03.csv absent).
2. The agent proved its fix: a completed, non-seeded run exists for every day still in data/.
3. The grader restores this morning's export and runs the agent's entrypoint on it in a fresh process: the run
   completes and its summary equals the reference's (every row counted, separators parsed).
4. Hidden exports, one per fault class, one clean, one with both, each in a fresh process after expiring every
   step run as a cache candidate: fixing only one cause, dropping rows, widening the region list, or deleting
   the row-accounting check all fail here.
5. Seeded runs untouched (ids from the manifest, statuses, step statuses, the two tracebacks still there).
6. The shipped exports are byte-identical (sha256 manifest).
7. No pipeline other than `daily_report` is registered.
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
QUARANTINED = ["2026-09-03", "2026-09-09"]
ON_DISK = ["2026-09-02", "2026-09-04", "2026-09-06", "2026-09-07", "2026-09-08"]
HIDDEN = {"2026-08-20": "hidden_plain", "2026-08-21": "hidden_sep", "2026-08-22": "hidden_region", "2026-08-23": "hidden_both"}
TOL = 0.011  # summaries are rounded to 2 dp; allow one unit in the last place either way
FAULTS = {"scheduled-2026-09-03": "summarise", "scheduled-2026-09-09": "parse"}  # seeded run -> step whose traceback must survive


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


def run_entrypoint(date: str) -> Any:
    """Expire every step run as a cache candidate, run the agent's code on `date` in a fresh process, return the one new run."""
    c = Client()
    for run in all_runs():
        for step in run.steps.values():
            c.update_step_run(step.id, cache_expires_at=datetime.now(timezone.utc))
    seen = {r.id for r in all_runs()}
    proc = subprocess.run([sys.executable, "run.py", "--date", date], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"entrypoint failed on {date}:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in all_runs() if r.id not in seen]
    assert len(new) == 1, f"expected exactly one new run, found {len(new)}"
    assert new[0].status == ExecutionStatus.COMPLETED and new[0].pipeline.name == PIPELINE and load_date(new[0]) == date
    return new[0]


@pytest.fixture(scope="module")
def seeded() -> dict[str, dict[str, Any]]:
    assert SEED_RUNS.exists(), f"seed manifest missing at {SEED_RUNS}"
    return {s["id"]: s for s in json.loads(SEED_RUNS.read_text())}


@pytest.fixture(scope="module")
def runs_before(seeded) -> list[Any]:
    """Snapshot of the store before the grader runs anything; also records the agent's run counts as metrics."""
    runs = all_runs()
    agent = [r for r in runs if str(r.id) not in seeded]
    write_metrics(agent_runs=len(agent), agent_failed_runs=sum(r.status == ExecutionStatus.FAILED for r in agent),
                  agent_runs_for_quarantined=sum(load_date(r) in QUARANTINED for r in agent),
                  agent_completed_days=len({load_date(r) for r in agent if r.status == ExecutionStatus.COMPLETED}),
                  seeded_runs_seen=sum(str(r.id) in seeded for r in runs))
    return runs


def test_no_export_fabricated_for_a_quarantined_day(runs_before):
    """Check 1: the failed days' exports are gone; the agent must not have written stand-ins (runs first, before the grader restores one)."""
    present = [d for d in QUARANTINED if (APP_DIR / "data" / f"{d}.csv").exists()]
    assert not present, f"data/ holds an export the agent wrote for a quarantined day: {present}"


def test_agent_proved_the_fix_on_every_day_on_disk(runs_before, seeded):
    """Check 2: for each export still in data/, a completed run the agent made (not seeded)."""
    done = {load_date(r) for r in runs_before if str(r.id) not in seeded and r.status == ExecutionStatus.COMPLETED}
    missing = [d for d in ON_DISK if d not in done]
    assert not missing, f"no completed run by the agent for {missing}; the instruction asked for one per export in data/"


def test_restored_export_completes_with_every_row(runs_before):
    """Check 3: ops restore this morning's export; the agent's code must complete on it with the reference summary."""
    shutil.copy(FIXTURES / f"{TARGET_DATE}.csv", APP_DIR / "data" / f"{TARGET_DATE}.csv")
    run = run_entrypoint(TARGET_DATE)
    expected = json.loads((FIXTURES / "expected.json").read_text())
    got = summary_of(run)
    assert same_summary(got, expected), f"summary for the restored {TARGET_DATE} differs from the reference:\n got {got}\n exp {expected}"
    assert (APP_DIR / "reports" / f"{TARGET_DATE}.json").exists(), "reports/<date>.json was not written"


@pytest.mark.parametrize("hidden_date", list(HIDDEN))
def test_hidden_export_in_fresh_process(runs_before, hidden_date):
    """Check 4: exports the agent never saw: clean, separators elsewhere, region spellings elsewhere, both at once."""
    shutil.copy(FIXTURES / f"{HIDDEN[hidden_date]}.csv", APP_DIR / "data" / f"{hidden_date}.csv")
    run = run_entrypoint(hidden_date)
    expected = json.loads((FIXTURES / f"expected_{HIDDEN[hidden_date]}.json").read_text())
    got = summary_of(run)
    assert same_summary(got, expected), f"summary on the hidden export {HIDDEN[hidden_date]} differs from the reference:\n got {got}\n exp {expected}"
    assert (APP_DIR / "reports" / f"{hidden_date}.json").exists(), "reports/<date>.json was not written"


def test_seeded_history_untouched(runs_before, seeded):
    """Check 5: the original runs still exist with their statuses, step statuses and the two recorded tracebacks."""
    by_id = {str(r.id): r for r in runs_before}
    for sid, s in seeded.items():
        r = by_id.get(sid)
        assert r is not None, f"seeded run {s['name']} was deleted"
        assert str(r.status) == s["status"], f"{r.name}: status {r.status}, seeded as {s['status']}"
        assert {n: str(st.status) for n, st in r.steps.items()} == s["steps"], f"{r.name}: step statuses changed"
        if s["name"] in FAULTS:
            info = r.steps[FAULTS[s["name"]]].exception_info
            assert info and "ValueError" in info.source, f"{r.name}: recorded traceback missing"


def test_shipped_exports_unchanged():
    """Check 6: the fix must be in the code, not in the exports still on disk."""
    manifest = json.loads((FIXTURES / "shipped_sha256.json").read_text())
    for name, digest in manifest.items():
        assert hashlib.sha256((APP_DIR / "data" / name).read_bytes()).hexdigest() == digest, f"data/{name} was modified"


def test_collateral():
    """Check 7: no stray pipelines."""
    assert {p.name for p in Client().list_pipelines(size=50).items} == {PIPELINE}
