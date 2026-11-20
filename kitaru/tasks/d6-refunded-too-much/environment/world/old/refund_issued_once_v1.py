from kitaru.task.evaluator import EvaluationResult, SessionView


def evaluate(session: SessionView, **params) -> EvaluationResult:
    """Pass when the conversation called the refund tool at most once."""
    refunds = [n for n in session.nodes if n.node_type == "tool_call" and n.tool_name == "issue_refund"]
    return EvaluationResult(name="refund_issued_once", score=len(refunds), passed=len(refunds) <= 1, explanation=f"{len(refunds)} refund call(s)")
