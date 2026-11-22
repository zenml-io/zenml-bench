from kitaru.task.evaluator import EvaluationResult, SessionView


def evaluate(session: SessionView, **params) -> EvaluationResult:
    refunds = [n for n in session.nodes if n.node_type == "tool_call" and n.tool_name == "issue_refund"]
    return EvaluationResult(name="at_most_one_refund", score=len(refunds), passed=len(refunds) <= 1, explanation=f"{len(refunds)} refund call(s)")
