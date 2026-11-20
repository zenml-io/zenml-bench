from kitaru.task.evaluator import EvaluationResult, SessionView


def evaluate(session: SessionView, **params) -> EvaluationResult:
    """Pass when at most one refund was actually issued. Version 2: a refund call that the payment
    service rejected no longer counts (version 1 counted every call)."""
    issued = [n for n in session.nodes if n.node_type == "tool_call" and n.tool_name == "issue_refund"
              and isinstance(n.outputs, dict) and n.outputs.get("status") == "issued"]
    return EvaluationResult(name="refund_issued_once", score=len(issued), passed=len(issued) <= 1, explanation=f"{len(issued)} refund(s) issued")
