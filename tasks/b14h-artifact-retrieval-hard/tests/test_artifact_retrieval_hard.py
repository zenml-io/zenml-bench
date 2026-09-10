"""Grader for B14H artifact-retrieval (hard).

The store holds real history (environment/setup_store.sh): finance's late-August backfill, in which three days
were processed twice because corrected exports arrived (one re-processing failed), then the cron week. The
correct artifact is derived here the way the instruction defines it: for every backfilled day, the most recent
COMPLETED `backfill` run of `daily_report` counts; among those, the largest summary total. Distractors, each
the answer under a different wrong rule: the first 08-26 processing (failed; largest summary of all), the first
08-27 processing (largest completed total; superseded), the failed 08-25 re-processing (latest per day if status
is ignored), scheduled 09-08 (largest completed total if the tag is ignored).

1. A completed `region_report` run exists with exactly one step; the most recent such run's step has the correct
   artifact version among its recorded inputs (any input type: passed in, or loaded with `load_artifact`).
2. reports/region_top.json names that summary's top region and total, and cites the artifact's name and
   version number as ZenML recorded them.
3. Seeded runs untouched (ids from the manifest, statuses, tags, step statuses) and no new `daily_report` run.
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
    """(artifact version, summary) that counts for the busiest backfilled day."""
    runs = Client().list_pipeline_runs(pipeline=SOURCE, tags=["backfill"], sort_by="asc:created", size=100).items
    latest: dict[str, Any] = {}
    for r in runs:
        if r.status == ExecutionStatus.COMPLETED:
            latest[str(r.steps["load"].config.parameters["date"])] = r  # ascending order: the last completed run of a day wins
    assert latest, "no completed backfill runs in the store"
    date, run = max(latest.items(), key=lambda dr: dr[1].steps["summarise"].outputs["output"][0].load()["total"])
    version = run.steps["summarise"].outputs["output"][0]
    expected = json.loads((FIXTURES / "expected.json").read_text())
    assert date == expected["date"] and str(version.version) == expected["artifact_version"], "seeded history differs from the fixture"
    return version, version.load()


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
    inputs = [(name, str(v.id), str(v.input_type), f"{v.artifact.name} v{v.version}") for name, vs in step.inputs.items() for v in vs]
    write_metrics(input_types=len({t for _, _, t, _ in inputs}))
    assert str(version.id) in {i for _, i, _, _ in inputs}, f"step inputs {inputs} do not include the summary that counts, {version.artifact.name} v{version.version} ({version.id})"


def test_report_names_top_region_and_cites_the_version(correct):
    version, summary = correct
    region, stats = max(summary["regions"].items(), key=lambda kv: kv[1]["total"])
    report = json.loads((APP_DIR / "reports" / "region_top.json").read_text())
    assert report.get("region") == region, f"report region {report.get('region')!r}, expected {region!r}"
    assert abs(float(report.get("total", -1)) - stats["total"]) <= TOL, f"report total {report.get('total')}, expected {stats['total']}"
    assert report.get("artifact_name") == version.artifact.name, f"report cites artifact {report.get('artifact_name')!r}, expected {version.artifact.name!r}"
    assert str(report.get("artifact_version")) == str(version.version), f"report cites version {report.get('artifact_version')!r}, expected {version.version!r}"


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
