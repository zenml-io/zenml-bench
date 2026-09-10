"""Grader for R1-bare. Mirrors R1's checks on results.tsv + best_model.pkl instead of the ZenML store."""
from typing import Any

import pytest

import verify_bare as verify

BUDGET, PASS_LINE = 12, 0.5


@pytest.fixture(scope="module")
def facts() -> dict[str, Any]:
    f = verify.audit()
    verify.write_metrics(f)
    print(f)
    return f


def test_budget(facts):
    assert 1 <= facts["experiments"] <= BUDGET, f"{facts['experiments']} rows in results.tsv; budget is {BUDGET}"


def test_promotion_is_backed_by_a_row(facts):
    assert facts["promoted"] is not None, "no best_model.pkl"
    assert facts["backing_row"] is not None, "best_model.pkl is not byte-identical to any results.tsv row's model file"


def test_backing_row_trained_on_its_seed_slice(facts):
    assert facts["slice_violation"] is None, facts["slice_violation"]


def test_promoted_model_loads_and_scores(facts):
    assert facts["load_error"] is None, facts["load_error"]
    assert facts["hidden_log_loss"] is not None


def test_gap_closed(facts):
    assert facts["gap_closed"] >= PASS_LINE, f"gap_closed={facts['gap_closed']:.3f} (hidden log loss {facts['hidden_log_loss']})"
