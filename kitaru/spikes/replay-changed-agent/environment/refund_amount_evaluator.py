from kitaru.task.evaluator import EvaluationResult, SessionView


def evaluate(session: SessionView, **params) -> EvaluationResult:
    """Pass when every refund was for the amount the order lookup returned."""
    tools = [n for n in session.nodes if n.node_type == "tool_call"]
    amounts = [n.outputs["amount"] for n in tools if n.tool_name == "lookup_order" and isinstance(n.outputs, dict)]
    refunds = [n.inputs["amount"] for n in tools if n.tool_name == "issue_refund"]
    ok = all(r == amounts[-1] for r in refunds) if amounts else not refunds
    return EvaluationResult(name="refund_matches_order", score=ok, passed=ok, explanation=f"order amounts {amounts}, refunds {refunds}")
