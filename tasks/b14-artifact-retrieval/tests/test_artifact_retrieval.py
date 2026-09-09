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
from pathlib import Path
from typing import Any

import pytest
from zenml.client import Client
from zenml.enums import ExecutionStatus

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


def test_collateral():
    assert {p.name for p in Client().list_pipelines(size=50).items} == {SOURCE, NEW}
