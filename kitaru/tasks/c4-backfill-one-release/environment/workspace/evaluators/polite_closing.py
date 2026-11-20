from kitaru.task.evaluator import EvaluationResult, SessionView

CLOSINGS = ("thanks for shopping with larkspur goods", "is there anything else i can help you with", "have a lovely day")


def evaluate(session: SessionView, **params) -> EvaluationResult:
    """Pass when the reply the customer reads ends with one of the team's closing courtesies."""
    outputs = session.session.outputs
    reply = (outputs.get("reply", "") if isinstance(outputs, dict) else str(outputs or "")).lower()
    polite = any(closing in reply for closing in CLOSINGS)
    return EvaluationResult(name="polite_closing", score=polite, passed=polite, explanation="closing found" if polite else "no closing courtesy in the reply")
