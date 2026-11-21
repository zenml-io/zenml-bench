import re

from kitaru.task.evaluator import EvaluationResult, SessionView

UNITS = {"USD": 100, "EUR": 100, "GBP": 100, "JPY": 1}  # how many of the smallest unit make one of the currency


def evaluate(session: SessionView, **params) -> EvaluationResult:
    """Pass when the refund a conversation paid is what the customer asked back: the line of one item (unit price times
    quantity, less the line's discount) when the message asks for one item, otherwise the order's total less what was
    already credited. A conversation that paid no refund passes."""
    orders = [n.outputs for n in session.nodes if n.node_type == "tool_call" and n.tool_name == "lookup_order" and isinstance(n.outputs, dict) and "total_minor" in n.outputs]
    refunds = [n.inputs for n in session.nodes if n.node_type == "tool_call" and n.tool_name == "issue_refund" and isinstance(n.inputs, dict)]
    if not refunds or not orders:
        return EvaluationResult(name="refund_amount", score=1, passed=True, explanation="no refund")
    order = orders[-1]
    only = re.search(r"refund only the ([a-z ]+)\.", str(session.session.inputs or ""))
    if only:
        line = next(i for i in order["items"] if i["name"] == only.group(1))
        owed = line["unit_minor"] * line["quantity"] - line["discount_minor"]
    else:
        owed = order["total_minor"] - order["credited_minor"]
    expected = owed / UNITS[order["currency"]]
    wrong = [r for r in refunds if abs(float(r.get("amount", -1)) - expected) > 0.005 or r.get("currency") != order["currency"]]
    return EvaluationResult(name="refund_amount", score=int(not wrong), passed=not wrong,
                            explanation=f"expected {expected} {order['currency']}; paid {[(r.get('amount'), r.get('currency')) for r in refunds]}")
