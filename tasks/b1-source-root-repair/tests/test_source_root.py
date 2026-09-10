"""Grader for B1 source-root-repair. Runs both documented entrypoints itself and reads the store and the filesystem.

Facts (docs/decisions.md 2026-09-10): ZenML's source root is the repository (`.zen`) found from the CWD upward,
else the main module's directory; a step's recorded source (`step.spec.source.import_path`) is relative to that
root, so a stray repository in `jobs/backfill` records `run.load_history`, which `source_utils.load` cannot import
from the project root. ZenML does not add the repository root to sys.path, so the import fix is the agent's. Runs and pipelines are
listed across ALL ZenML projects: an agent may isolate the analytics pipelines in their own project (first Codex
baseline did `zenml project register analytics --set`), and a client's default listing only covers its active project.
Env: APP_DIR (default /app; the workspace holding analytics/ and legacy_reports/).
"""
import hashlib
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

APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
ANALYTICS, LEGACY = APP_DIR / "analytics", APP_DIR / "legacy_reports"
ENTRYPOINTS = {"daily_analytics": (ANALYTICS, ["pipelines/daily.py"]), "backfill_analytics": (ANALYTICS / "jobs" / "backfill", ["run.py"])}
PREFIX = {"daily_analytics": "pipelines.daily.", "backfill_analytics": "jobs.backfill.run."}
MANIFEST = [Path(os.environ.get("ZENML_CONFIG_PATH", "/nonexistent")) / "seed_b1.json", Path("/var/lib/zenml-bench/seed_b1.json")]
LOADER = "from zenml.utils.source_utils import load\nimport sys\nload(sys.argv[1])\n"


def all_runs() -> list[Any]:
    c = Client()
    return [r for p in c.list_projects(size=100).items for r in c.list_pipeline_runs(project=p.id, size=500).items]


def all_pipelines() -> set[str]:
    c = Client()
    return {x.name for p in c.list_projects(size=100).items for x in c.list_pipelines(project=p.id, size=100).items}


def run_entrypoint(cwd: Path, argv: list[str]) -> Any:
    seen = {r.id for r in all_runs()}
    proc = subprocess.run([sys.executable, *argv], cwd=cwd, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"{' '.join(argv)} in {cwd} failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in all_runs() if r.id not in seen]
    assert len(new) == 1, f"expected exactly one new run, found {len(new)}"
    return Client().get_pipeline_run(new[0].id)


def loads_from(root: Path, source: str) -> bool:
    return subprocess.run([sys.executable, "-c", LOADER, source], cwd=root, capture_output=True, text=True, timeout=300).returncode == 0


@pytest.fixture(scope="module")
def runs() -> dict[str, Any]:
    return {name: run_entrypoint(cwd, argv) for name, (cwd, argv) in ENTRYPOINTS.items()}


@pytest.fixture(scope="module")
def seed() -> dict[str, Any]:
    for p in MANIFEST:
        if p.exists():
            return json.loads(p.read_text())
    return {}


def test_both_entrypoints_complete(runs):
    df = pd.read_csv(ANALYTICS / "data" / "visits.csv")
    expected = round(float((df["spend"] / df["visits"].clip(lower=1)).mean()), 4)
    for name, r in runs.items():
        assert r.status == ExecutionStatus.COMPLETED and r.pipeline.name == name
        assert set(r.steps) == {"load" if name == "daily_analytics" else "load_history", "build_features", "summarise"}, f"{name} steps are {list(r.steps)}"
        summary = r.steps["summarise"].outputs["summary"][0].load()
        assert summary["rows"] == len(df) and summary["mean_spend_per_visit"] == pytest.approx(expected, abs=1e-4)


def test_step_sources_resolve_from_the_project_root(runs):
    for name, r in runs.items():
        for step_name, st in r.steps.items():
            src = st.spec.source.import_path
            assert loads_from(ANALYTICS, src), f"{name}.{step_name} was recorded as {src!r}, which does not import from {ANALYTICS} (wrong source root)"
        entry_src = r.steps["load" if name == "daily_analytics" else "load_history"].spec.source.import_path
        assert entry_src.startswith(PREFIX[name]), f"{name} entry step recorded as {entry_src!r}, expected {PREFIX[name]}…"


def test_repository_is_at_the_analytics_root():
    assert (ANALYTICS / ".zen").is_dir(), "no ZenML repository at /app/analytics"
    strays = [p for p in ANALYTICS.rglob(".zen") if p != ANALYTICS / ".zen"]
    assert not strays, f"extra ZenML repositories under analytics: {[str(p) for p in strays]}"
    assert not (APP_DIR / ".zen").exists(), "a ZenML repository at the workspace root would shadow both projects"


def test_neighbour_untouched(seed):
    assert (LEGACY / ".zen").is_dir(), "legacy_reports lost its ZenML repository"
    files = {str(p.relative_to(LEGACY)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(LEGACY.rglob("*")) if p.is_file() and ".zen" not in p.parts and "__pycache__" not in p.parts}
    if seed:
        assert files == seed["legacy_files"], "files under legacy_reports changed"
        assert Client().get_pipeline_run(seed["legacy_run_id"]).status == ExecutionStatus.COMPLETED, "the neighbour's recorded run is gone"
    r = run_entrypoint(LEGACY, ["report.py"])
    assert r.status == ExecutionStatus.COMPLETED and r.pipeline.name == "legacy_report"
    assert all(st.spec.source.import_path.startswith("report.") for st in r.steps.values()), "legacy_reports now resolves against a different root"


def test_runs_are_genuine(runs):
    """Defeats a forger that rewrites recorded step sources in SQLite after each run (tests/shortcuts/tamper_store.sh)."""
    for r in runs.values():
        assert_genuine_run(r)


def test_collateral():
    assert all_pipelines() == {"daily_analytics", "backfill_analytics", "legacy_report"}
