"""Grader for B6 model-promotion. Everything is read from the ZenML store or computed from artifacts it holds.

Facts (docs/decisions.md 2026-09-10): a run's `model_version` is the version the pipeline's Model resolved to; the
model version is NOT part of the step cache key, so a cached `predict` can carry an older version's predictions
under a run linked to the new one. The grader therefore scores predictions against the linked version's own model
artifact, never the link alone. A promotion with force archives the previous production version.
Sequence: (1) production == lowest val_mae; (2) the agent's inference run is linked to it and its predictions come
from it; (3) grader run on a hidden batch; (4) grader promotes the worst version and reruns on the same hidden
batch: predictions must now come from that version. Seeded versions and their metrics must be unchanged.
Env: APP_DIR (default /app/model_promotion), FIXTURES_DIR (default /tests/fixtures).
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

APP_DIR = Path(os.environ.get("APP_DIR", "/app/model_promotion"))
FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
MODEL, TRAIN_PIPE, INFER_PIPE = "demand_forecaster", "train_forecaster", "batch_forecast"
FEATURES = ["store_id", "promo", "price", "temp_c", "dow"]
HIDDEN = FIXTURES / "hidden_batch.csv"
MANIFEST = [Path(os.environ.get("ZENML_CONFIG_PATH", "/nonexistent")) / "seed_versions.json", Path("/var/lib/zenml-bench/seed_versions.json")]


def versions() -> list[Any]:
    return Client().list_model_versions(model=MODEL, size=50, sort_by="asc:number").items


def mae(mv: Any) -> float:
    return float(mv.run_metadata["val_mae"])


def predict_with(mv: Any, batch: pd.DataFrame) -> list[float]:
    model = mv.get_model_artifact("model").load()
    return [round(float(x), 2) for x in model.predict(batch[FEATURES])]


def run_predictions(run: Any) -> list[float]:
    return [float(x) for x in run.steps["predict"].outputs["predictions"][0].load()["units_pred"]]


def run_batch(run: Any) -> pd.DataFrame:
    return run.steps["load_batch"].outputs["batch"][0].load()


def run_inference(input_path: Path) -> Any:
    seen = {r.id for r in Client().list_pipeline_runs(size=500).items}
    proc = subprocess.run([sys.executable, "inference.py", "--input", str(input_path)], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"inference entrypoint failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in Client().list_pipeline_runs(sort_by="desc:created", size=5).items if r.id not in seen]
    assert len(new) == 1, f"expected exactly one new run, found {len(new)}"
    return new[0]


@pytest.fixture(scope="module")
def production() -> Any:
    try:
        return Client().get_model_version(MODEL, "production")
    except KeyError:
        pytest.fail("no version of demand_forecaster is in the production stage")


@pytest.fixture(scope="module")
def seed() -> list[dict[str, Any]]:
    for p in MANIFEST:
        if p.exists():
            return json.loads(p.read_text())
    return []


def test_production_is_the_best_version(production):
    best = min(versions(), key=mae)
    assert production.id == best.id, f"production is version {production.number} (val_mae {mae(production):.4f}); the lowest val_mae is version {best.number} ({mae(best):.4f})"


def test_agents_inference_run_used_production(production):
    runs = [r for r in Client().list_pipeline_runs(pipeline=INFER_PIPE, size=100, sort_by="desc:created").items if r.status == ExecutionStatus.COMPLETED]
    assert runs, "no completed batch_forecast run"
    linked = [r for r in runs if r.model_version and r.model_version.id == production.id]
    assert linked, f"no completed batch_forecast run is linked to production version {production.number}"
    ok = [r for r in linked if run_predictions(r) == pytest.approx(predict_with(production, run_batch(r)), abs=1e-6)]
    assert ok, "a run is linked to the production version but its predictions were not made by that version's model (cached predict from an earlier version?)"
    assert_genuine_run(ok[-1])  # tests/shortcuts/tamper_store.sh writes such a run by hand (manual artifacts, forged link)


def test_hidden_batch_uses_production(production):
    run = run_inference(HIDDEN)
    assert run.status == ExecutionStatus.COMPLETED
    assert run.model_version and run.model_version.id == production.id, f"grader run linked to version {run.model_version.number if run.model_version else None}"
    assert run_predictions(run) == pytest.approx(predict_with(production, pd.read_csv(HIDDEN)), abs=1e-6), "predictions on the hidden batch are not the production model's"
    assert_genuine_run(run)


def test_next_run_follows_a_new_promotion(production):
    other = max(versions(), key=mae)
    assert other.id != production.id
    other.set_stage("production", force=True)
    run = run_inference(HIDDEN)
    assert run.status == ExecutionStatus.COMPLETED
    assert run.model_version and run.model_version.id == other.id, f"after promoting version {other.number}, the run is linked to {run.model_version.number if run.model_version else None}"
    assert run_predictions(run) == pytest.approx(predict_with(other, pd.read_csv(HIDDEN)), abs=1e-6), f"after promoting version {other.number} the predictions still come from another version (hardcoded version or cached predict)"
    assert_genuine_run(run)
    try:
        Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
        Path("/logs/verifier/metrics.json").write_text(json.dumps({"predict_cached_after_repromotion": int(run.steps["predict"].status == ExecutionStatus.CACHED)}))
    except OSError:
        pass


def test_seeded_versions_untouched(seed):
    by_number = {v.number: v for v in versions()}
    for s in seed:
        mv = by_number.get(s["number"])
        assert mv is not None and str(mv.id) == s["id"], f"seeded version {s['number']} is missing or replaced"
        assert mae(mv) == pytest.approx(s["val_mae"], abs=1e-9), f"val_mae of version {s['number']} was changed"
    assert len(by_number) == len(seed) or not seed, f"{len(by_number)} versions registered; {len(seed)} were seeded (no new training allowed)"


def test_collateral():
    assert {p.name for p in Client().list_pipelines(size=50).items} == {TRAIN_PIPE, INFER_PIPE}
