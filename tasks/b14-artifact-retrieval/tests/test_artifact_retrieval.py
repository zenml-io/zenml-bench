"""Grader for B14 artifact-retrieval.

The store holds real history (environment/setup_store.sh). The correct artifact is computed here the way the
instruction defines it: the `summarise` output of the COMPLETED `daily_report` run tagged `backfill` with the
largest summary total (ids differ per image build, so it is derived, not stored). Distractors: a failed backfill
run whose summary total is the largest of all; a completed scheduled run that beats every backfill day.

1. A completed `region_report` run exists with exactly one step; the most recent such run's step has the correct
   artifact version among its recorded inputs (any input type: passed in, or loaded with `load_artifact`).
2. reports/region_top.json names that summary's top region and its total.
3. Seeded runs untouched (names, statuses, tags; ids when the manifest is present).
4. Only `daily_report` and `region_report` are registered.
Env: APP_DIR, FIXTURES_DIR, SEED_RUNS_PATH as in B10.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from zenml import save_artifact
from zenml.client import Client
from zenml.enums import ExecutionStatus

from store_integrity import assert_genuine_run

APP_DIR = Path(os.environ.get("APP_DIR", "/app/daily_report"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
SEED_RUNS = Path(os.environ.get("SEED_RUNS_PATH") or Path(os.environ.get("ZENML_CONFIG_PATH", "/var/lib/zenml-bench")) / "seed_runs.json")
SOURCE, NEW = "daily_report", "region_report"
TOL = 0.011


def write_metrics(**kv: Any) -> None:
    try:
        p = Path("/logs/verifier/metrics.json"); p.parent.mkdir(parents=True, exist_ok=True)
        old = json.loads(p.read_text()) if p.exists() else {}
        p.write_text(json.dumps(old | kv))
    except OSError:
        pass


def run_entrypoint(argv: list[str]) -> Any:
    """Run the agent's entrypoint in a fresh process and return the one `region_report` run it created."""
    seen = {r.id for r in Client().list_pipeline_runs(size=500).items}
    (APP_DIR / "reports" / "region_top.json").unlink(missing_ok=True)
    proc = subprocess.run([sys.executable, "region_report.py", *argv], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"entrypoint failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in Client().list_pipeline_runs(sort_by="desc:created", size=10).items if r.id not in seen]
    assert len(new) == 1 and new[0].pipeline.name == NEW, f"expected exactly one new {NEW} run, found {[(r.name, r.pipeline.name) for r in new]}"
    return new[0]


def step_input_ids(run: Any) -> set[str]:
    assert len(run.steps) == 1, f"{NEW} must have exactly one step, has {list(run.steps)}"
    step = next(iter(run.steps.values()))
    return {str(v.id) for vs in step.inputs.values() for v in vs}


@pytest.fixture(scope="module")
def correct() -> tuple[Any, dict[str, Any]]:
    """(artifact version, summary) of the completed backfill run with the largest total."""
    runs = [r for r in Client().list_pipeline_runs(pipeline=SOURCE, tags=["backfill"], size=100).items if r.status == ExecutionStatus.COMPLETED]
    assert runs, "no completed backfill runs in the store"
    candidates = [(r.steps["summarise"].outputs["output"][0], r) for r in runs]
    version, run = max(candidates, key=lambda vr: vr[0].load()["total"])
    summary = version.load()
    expected = json.loads((FIXTURES / "expected.json").read_text())
    assert run.steps["load"].config.parameters["date"] == expected["date"], "seeded history differs from the fixture"
    return version, summary


@pytest.fixture(scope="module")
def new_run() -> Any:
    runs = [r for r in Client().list_pipeline_runs(pipeline=NEW, sort_by="desc:created", size=100).items]
    completed = [r for r in runs if r.status == ExecutionStatus.COMPLETED]
    write_metrics(region_report_runs=len(runs), region_report_completed=len(completed))
    assert completed, f"no completed {NEW} run; runs: {[(r.name, str(r.status)) for r in runs]}"
    return completed[0]


def test_one_step_with_the_historical_artifact_as_input(new_run, correct):
    version, _ = correct
    assert len(new_run.steps) == 1, f"{NEW} must have exactly one step, has {list(new_run.steps)}"
    step = next(iter(new_run.steps.values()))
    inputs = [(name, str(v.id), str(v.input_type)) for name, vs in step.inputs.items() for v in vs]
    write_metrics(input_types=len({t for _, _, t in inputs}))
    assert str(version.id) in {i for _, i, _ in inputs}, f"step inputs {inputs} do not include the summary artifact version {version.id} (v{version.version})"


def test_report_names_top_region(correct):
    _, summary = correct
    region, stats = max(summary["regions"].items(), key=lambda kv: kv[1]["total"])
    report = json.loads((APP_DIR / "reports" / "region_top.json").read_text())
    assert report.get("region") == region, f"report region {report.get('region')!r}, expected {region!r}"
    assert abs(float(report.get("total", -1)) - stats["total"]) <= TOL, f"report total {report.get('total')}, expected {stats['total']}"


def test_seeded_history_untouched():
    assert SEED_RUNS.exists(), f"seed manifest missing at {SEED_RUNS}"
    seeded = json.loads(SEED_RUNS.read_text())
    runs = {str(r.id): r for r in Client().list_pipeline_runs(pipeline=SOURCE, size=500).items}
    for s in seeded:
        r = runs.get(s["id"])
        assert r is not None, f"seeded run {s['name']} was deleted"
        assert str(r.status) == s["status"] and sorted(t.name for t in r.tags) == s["tags"], f"{s['name']} changed"
        assert {n: str(st.status) for n, st in r.steps.items()} == s["steps"], f"{s['name']}: step statuses changed"
    assert len(runs) == len(seeded), f"{len(runs) - len(seeded)} extra {SOURCE} run(s): the instruction said not to run it"


def test_hidden_summary_through_the_entrypoint(new_run, correct):
    """Re-execution on a hidden input. The store is writable by the agent (tests/shortcuts/tamper_store.sh inserts a
    forged input row under a run that hardcoded the numbers), so the grader stores a summary the agent never saw as
    an artifact version of its own, runs the agent's entrypoint on it, and checks that the report describes it, that
    the run consumed it, and that the run's records were produced by ZenML."""
    hidden = json.loads((FIXTURES / "hidden_summary.json").read_text())
    av = save_artifact(hidden, name=f"grader_summary_{uuid4().hex[:6]}")
    daily_before = {r.id for r in Client().list_pipeline_runs(pipeline=SOURCE, size=500).items}
    run = run_entrypoint([str(av.id)])
    assert run.status == ExecutionStatus.COMPLETED
    assert_genuine_run(run)
    assert str(av.id) in step_input_ids(run), "the entrypoint's run did not take the grader's artifact version as its step input"
    region, stats = max(hidden["regions"].items(), key=lambda kv: kv[1]["total"])
    report = json.loads((APP_DIR / "reports" / "region_top.json").read_text())
    assert report.get("region") == region and abs(float(report.get("total", -1)) - stats["total"]) <= TOL, f"report {report} does not describe the grader's summary"
    assert {r.id for r in Client().list_pipeline_runs(pipeline=SOURCE, size=500).items} == daily_before, "the entrypoint ran daily_report"
    assert_genuine_run(new_run)


def test_collateral():
    assert {p.name for p in Client().list_pipelines(size=50).items} == {SOURCE, NEW}
