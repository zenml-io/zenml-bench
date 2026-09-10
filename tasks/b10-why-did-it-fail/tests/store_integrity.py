"""Checks that a pipeline run in the ZenML store was produced by ZenML's own execution, not written by hand.

Copied into every non-research task's tests/ by scripts/sync_checks.sh (Harbor uploads tests/ alone), so edit
the copy under shared/checks/ and re-sync. The invariants below were observed on ZenML 0.96.4 (docs/decisions.md,
2026-09-10 "store tampering inventory"):

- a COMPLETED step's output artifact versions have save_type == step_output and producer_step_run_id == the step's
  own id, and the step has a cache_key; a hand-saved artifact (`save_artifact`) is save_type == manual;
- a CACHED step records original_step_run_id, which is a COMPLETED step in a different run with the same cache key,
  and its outputs are the very same artifact versions as the original's (same ids). A step whose status was flipped
  to "cached" in SQLite after really executing leaves a fresh artifact behind and has no original;
- every artifact version's uri exists on disk (local artifact store).

What this does NOT defeat: a forger that also writes original_step_run_id, re-links the step_run_output_artifact
rows and creates artifact versions with save_type=step_output through the store API. That is re-implementing
ZenML's bookkeeping; the point is that it costs more than running the pipeline.
"""
from pathlib import Path
from typing import Any

from zenml.client import Client
from zenml.enums import ArtifactSaveType, ExecutionStatus

COMPLETED, CACHED = ExecutionStatus.COMPLETED, ExecutionStatus.CACHED


def output_ids(step: Any) -> dict[str, list[str]]:
    return {k: sorted(str(v.id) for v in vs) for k, vs in step.outputs.items()}


def assert_genuine_step(run: Any, name: str, step: Any) -> None:
    label = f"{run.name}.{name}"
    if step.status == COMPLETED:
        assert step.cache_key, f"{label}: completed step has no cache key (not produced by a ZenML execution)"
        for key, versions in step.outputs.items():
            for v in versions:
                assert v.save_type == ArtifactSaveType.STEP_OUTPUT, f"{label}.{key}: artifact {v.id} is save_type={v.save_type}, not a step output"
                assert v.producer_step_run_id == step.id, f"{label}.{key}: artifact {v.id} was produced by another step run ({v.producer_step_run_id})"
                assert not str(v.uri).startswith("/") or Path(v.uri).exists(), f"{label}.{key}: artifact uri {v.uri} does not exist"
    elif step.status == CACHED:
        assert step.original_step_run_id, f"{label}: marked cached but records no original step run"
        orig = Client().get_run_step(step.original_step_run_id)
        assert orig.status == COMPLETED, f"{label}: original step run {orig.id} is {orig.status}, not completed"
        assert orig.pipeline_run_id != run.id, f"{label}: original step run is in the same run"
        assert orig.cache_key == step.cache_key, f"{label}: cache key differs from the original step run's"
        assert output_ids(step) == output_ids(orig), f"{label}: cached step outputs {output_ids(step)} are not the original's {output_ids(orig)} (a real cache hit reuses the same artifact versions)"
        for key, versions in step.outputs.items():
            for v in versions:
                assert v.save_type == ArtifactSaveType.STEP_OUTPUT and v.producer_step_run_id == orig.id, f"{label}.{key}: artifact {v.id} is not the original step's output"
    else:
        raise AssertionError(f"{label}: status {step.status}")


def assert_genuine_run(run: Any) -> None:
    """Every step of a COMPLETED run was either executed by ZenML or served by a real cache hit."""
    assert run.status == COMPLETED, f"{run.name}: status {run.status}"
    assert run.steps, f"{run.name}: no step runs"
    for name, step in run.steps.items():
        assert_genuine_step(run, name, step)
