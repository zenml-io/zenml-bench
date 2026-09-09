"""Grader for R1 improve-within-budget. Reward 1 iff every test passes; verify.audit() supplies the facts.
Env: APP_DIR is unused (nothing is re-run); FIXTURES_DIR (default /tests/fixtures)."""
from typing import Any

import pytest

import verify

BUDGET, PASS_LINE = 12, 0.5


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


def test_promoted_model_loads_and_scores(facts):
    assert facts["load_error"] is None, facts["load_error"]
    assert facts["hidden_log_loss"] is not None


def test_gap_closed(facts):
    assert facts["gap_closed"] >= PASS_LINE, f"gap_closed={facts['gap_closed']:.3f} (hidden log loss {facts['hidden_log_loss']})"
