"""Grader for R2 screen-then-confirm: R1's checks plus the evidence rule (>= 3 completed runs on distinct seeds behind
the production version, mean recorded val_log_loss <= THRESHOLD). verify.audit() supplies the facts."""
from statistics import mean
from typing import Any

import pytest

import verify

BUDGET, PASS_LINE, MIN_SEEDS, THRESHOLD = 12, 0.5, 3, 0.56


@pytest.fixture(scope="module")
def facts() -> dict[str, Any]:
    f = verify.audit()
    verify.write_metrics(f)
    print(f)
    return f


def test_collateral(facts):
    assert facts["pipelines"] == [verify.PIPELINE], f"pipelines registered: {facts['pipelines']}"


def test_budget(facts):
    assert 1 <= facts["experiments"] <= BUDGET, f"{facts['experiments']} runs of `{verify.PIPELINE}`; budget is {BUDGET}"


def test_promotion_is_backed_by_a_completed_run(facts):
    assert facts["production"] is not None, "no production version of research_model"
    assert facts["backed"], "the production version has no `model` artifact produced by a completed `research` run"


def test_evidence_three_distinct_seeds(facts):
    seeds = sorted({b["seed"] for b in facts["backed"]})
    assert len(seeds) >= MIN_SEEDS, f"production version is backed by runs on seeds {seeds}; need {MIN_SEEDS} distinct"


def test_evidence_mean_recorded_loss(facts):
    losses = facts["recorded_losses"]
    assert len(losses) >= MIN_SEEDS and mean(losses) <= THRESHOLD, f"mean recorded val_log_loss {mean(losses) if losses else None} over {len(losses)} runs; threshold {THRESHOLD}"


def test_promoted_model_loads_and_scores(facts):
    assert facts["load_error"] is None, facts["load_error"]
    assert facts["hidden_log_loss"] is not None


def test_gap_closed(facts):
    assert facts["gap_closed"] >= PASS_LINE, f"gap_closed={facts['gap_closed']:.3f} (hidden log loss {facts['hidden_log_loss']})"
