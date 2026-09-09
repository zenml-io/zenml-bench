"""Frozen evaluator for the research tasks (R1/R2). Nothing the agent wrote is trusted as a source of metrics.

audit() reads the ZenML store and returns the facts the graders assert on, plus the metrics Harbor records:
- experiments: number of runs of the `research` pipeline, any status
- production version, the completed `research` runs linked to it, and the `model` artifacts those runs' `train`
  steps produced ("backed" artifacts); a hand-saved artifact has no producer step run and is ignored
- hidden_log_loss of the newest backed artifact, scored with THIS file's log loss on tests/fixtures/hidden.npz
- gap_closed = clip((baseline - agent) / (baseline - reference), 0, 1) against the seed-0 anchors in expected.json
- n_seeds_backing_promotion: distinct `seed` parameters of the backed completed runs
- recorded_losses: each backed run's own `val_log_loss` output (what the agent saw), for R2's mean rule
Env: FIXTURES_DIR (default /tests/fixtures).
"""
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
        "production": None, "backed": [], "n_seeds_backing_promotion": 0, "recorded_losses": [],
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
                facts["backed"].append({"artifact_id": str(av.id), "created": av.created.isoformat(), "run": run.name,
                                        "seed": train.config.parameters.get("seed"), "val_log_loss": loss})
    facts["backed"].sort(key=lambda b: b["created"])
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
               "experiments": facts["experiments"], "hidden_log_loss": facts["hidden_log_loss"]}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({k: v for k, v in metrics.items() if v is not None}))
    except OSError:
        pass


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, default=str))
