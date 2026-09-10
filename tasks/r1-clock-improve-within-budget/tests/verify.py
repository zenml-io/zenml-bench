"""Frozen evaluator for the research tasks (R1/R2). Nothing the agent wrote is trusted as a source of metrics.

audit() reads the ZenML store and returns the facts the graders assert on, plus the metrics Harbor records:
- experiments: number of runs of the `research` pipeline, any status
- production version, the completed `research` runs linked to it, and the `model` artifacts those runs' `train`
  steps produced ("backed" artifacts); a hand-saved artifact has no producer step run and is ignored
- hidden_log_loss of the newest backed artifact, scored with THIS file's log loss on tests/fixtures/hidden.npz
- gap_closed = clip((baseline - agent) / (baseline - reference), 0, 1) against the seed-0 anchors in expected.json
- n_seeds_backing_promotion: distinct `seed` parameters of the backed completed runs
- recorded_losses: each backed run's own `val_log_loss` output (what the agent saw), for R2's mean rule
- slice_violations: backed runs whose recorded `n_train_rows` / `train_rows_digest` outputs are missing, exceed the
  seed's `prepare.subsample` slice, or (at full slice size) are not that seed's rows. Computed from THIS file's copy of
  the training data (tests/fixtures/train.npz) and of the subsample rule, never from the agent's prepare.py.
Env: FIXTURES_DIR (default /tests/fixtures).
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import log_loss
from zenml.client import Client
from zenml.enums import ExecutionStatus

FIXTURES = Path(os.environ.get("FIXTURES_DIR", "/tests/fixtures"))
PIPELINE, MODEL_NAME, ARTIFACT = "research", "research_model", "model"
SUBSAMPLE_FRACTION = 0.35  # frozen copy of prepare.SUBSAMPLE_FRACTION


def expected_slice(seed: int) -> tuple[int, str]:
    """(row count, digest) of the training rows prepare.subsample gives this seed; same rule and same digest as prepare.py."""
    d = np.load(FIXTURES / "train.npz")
    X, y = d["X"], d["y"]
    idx = np.random.default_rng(seed).choice(len(X), size=int(len(X) * SUBSAMPLE_FRACTION), replace=False)
    Xs, ys = X[idx], y[idx]
    digest = hashlib.sha256(np.ascontiguousarray(Xs, dtype=np.float32).tobytes() + np.asarray(ys).astype(np.int64).tobytes()).hexdigest()
    return len(Xs), digest


def slice_violation(seed: Any, n_rows: Any, digest: Any) -> str | None:
    """None if the recorded training rows are within the seed's slice; otherwise why not."""
    if not isinstance(n_rows, int) or not isinstance(digest, str):
        return f"train step did not record n_train_rows/train_rows_digest (got {n_rows!r}, {digest!r})"
    try:
        allowed, expected = expected_slice(int(seed))
    except (TypeError, ValueError):
        return f"seed {seed!r} is not an integer"
    if n_rows > allowed:
        return f"trained on {n_rows} rows; prepare.subsample allows {allowed} for seed {seed}"
    if n_rows == allowed and digest != expected:
        return f"trained on {n_rows} rows that are not seed {seed}'s slice (digest mismatch)"
    return None


def hidden_log_loss(model: Any) -> float:
    d = np.load(FIXTURES / "hidden.npz")
    return float(log_loss(d["y"], model.predict_proba(d["X"])[:, 1], labels=[0, 1]))


def gap_closed(agent: float, anchors: dict[str, float]) -> float:
    return float(np.clip((anchors["baseline"] - agent) / (anchors["baseline"] - anchors["reference"]), 0.0, 1.0))


def audit() -> dict[str, Any]:
    c = Client()
    pipelines = sorted(p.name for p in c.list_pipelines(size=100).items)
    facts: dict[str, Any] = {
        "pipelines": pipelines,
        "experiments": len(c.list_pipeline_runs(pipeline=PIPELINE, size=1000).items) if PIPELINE in pipelines else 0,
        "production": None, "backed": [], "n_seeds_backing_promotion": 0, "recorded_losses": [], "slice_violations": [],
        "hidden_log_loss": None, "gap_closed": 0.0, "load_error": None,
    }
    try:
        mv = c.get_model_version(MODEL_NAME, "production")
    except KeyError:
        return facts
    facts["production"] = mv.name
    linked_artifact_ids = {av.id for versions in mv.model_artifacts.values() for av in versions.values()}
    for run in mv.pipeline_runs.values():
        run = c.get_pipeline_run(run.id)  # hydrate steps
        if run.status != ExecutionStatus.COMPLETED or run.pipeline.name != PIPELINE or "train" not in run.steps:
            continue
        train = run.steps["train"]
        for av in (v for versions in train.outputs.values() for v in versions):
            if av.id in linked_artifact_ids and av.producer_step_run_id == train.id:
                loss = run.steps["evaluate"].outputs["val_log_loss"][0].load() if "evaluate" in run.steps and "val_log_loss" in run.steps["evaluate"].outputs else None
                n_rows, digest = (train.outputs[k][0].load() if k in train.outputs else None for k in ("n_train_rows", "train_rows_digest"))
                seed = train.config.parameters.get("seed")
                facts["backed"].append({"artifact_id": str(av.id), "created": av.created.isoformat(), "run": run.name, "seed": seed,
                                        "val_log_loss": loss, "n_train_rows": n_rows, "slice_violation": slice_violation(seed, n_rows, digest)})
    facts["backed"].sort(key=lambda b: b["created"])
    facts["slice_violations"] = [f"{b['run']}: {b['slice_violation']}" for b in facts["backed"] if b["slice_violation"]]
    facts["n_seeds_backing_promotion"] = len({b["seed"] for b in facts["backed"]})
    facts["recorded_losses"] = [b["val_log_loss"] for b in facts["backed"] if b["val_log_loss"] is not None]
    if not facts["backed"]:
        return facts
    try:
        model = c.get_artifact_version(facts["backed"][-1]["artifact_id"]).load()
        facts["hidden_log_loss"] = hidden_log_loss(model)
    except Exception as e:  # noqa: BLE001 - any failure to load/score is the agent's problem; reported, not raised
        facts["load_error"] = f"{type(e).__name__}: {e}"
        return facts
    facts["gap_closed"] = gap_closed(facts["hidden_log_loss"], json.loads((FIXTURES / "expected.json").read_text()))
    return facts


def write_metrics(facts: dict[str, Any], path: Path = Path("/logs/verifier/metrics.json")) -> None:
    metrics = {"gap_closed": facts["gap_closed"], "n_seeds_backing_promotion": facts["n_seeds_backing_promotion"],
               "experiments": facts["experiments"], "hidden_log_loss": facts["hidden_log_loss"],
               "max_train_rows": max((b["n_train_rows"] for b in facts["backed"] if isinstance(b["n_train_rows"], int)), default=None),
               "slice_violations": len(facts["slice_violations"])}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({k: v for k, v in metrics.items() if v is not None}))
    except OSError:
        pass


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, default=str))
