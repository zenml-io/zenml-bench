from kitaru.task.evaluator import EvaluationResult, SessionView

DECIMALS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}  # digits after the point; the order service stores totals without it


def evaluate(session: SessionView, **params) -> EvaluationResult:
    """Pass when every refund the conversation asked for is the order's total, in the order's currency."""
    orders = [n.outputs for n in session.nodes if n.node_type == "tool_call" and n.tool_name == "lookup_order" and isinstance(n.outputs, dict) and "total_minor" in n.outputs]
    refunds = [n.inputs for n in session.nodes if n.node_type == "tool_call" and n.tool_name == "issue_refund" and isinstance(n.inputs, dict)]
    if not refunds or not orders:
        return EvaluationResult(name="refund_amount", score=1, passed=True, explanation="no refund")
    order = orders[-1]
    expected = order["total_minor"] / 10 ** DECIMALS[order["currency"]]
    wrong = [r for r in refunds if abs(float(r.get("amount", -1)) - expected) > 0.005 or r.get("currency") != order["currency"]]
    return EvaluationResult(name="refund_amount", score=int(not wrong), passed=not wrong,
                            explanation=f"expected {expected} {order['currency']}; asked for {[(r.get('amount'), r.get('currency')) for r in refunds]}")
