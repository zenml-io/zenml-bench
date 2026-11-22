from kitaru.task.evaluator import EvaluationResult, SessionView


def evaluate(session: SessionView, **params) -> EvaluationResult:
    """Pass when the conversation issued at most one refund."""
    refunds = [n for n in session.nodes if n.node_type == "tool_call" and n.tool_name == "issue_refund" and str(n.status).endswith("completed")]
    return EvaluationResult(name="refund_once", score=len(refunds), passed=len(refunds) <= 1, explanation=f"{len(refunds)} refund(s) issued")
