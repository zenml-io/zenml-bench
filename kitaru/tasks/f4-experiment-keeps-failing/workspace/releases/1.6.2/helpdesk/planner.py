"""What the assistant does next. In production a hosted model makes these decisions; in this repository the same
decisions are written out as a function, so the assistant behaves the same way every time it runs.

A request is one customer message. It names an order (`SO-12345`) and the customer's email address."""
import re
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo

from .money import to_major


def _call(tool: str, args: dict[str, Any], n: int) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool, args, tool_call_id=f"call_{n}")])


def _say(text: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(text)])


def next_step(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    requests = [m for m in messages if isinstance(m, ModelRequest)]
    returns = [p for m in requests for p in m.parts if isinstance(p, ToolReturnPart)]
    text = " ".join(str(getattr(p, "content", "")) for m in requests for p in m.parts if not isinstance(p, ToolReturnPart))
    order_id = re.search(r"SO-\d{5}", text).group()
    email = re.search(r"[\w.]+@[\w.]+\w", text).group()
    kind = "refund" if "refund" in text.lower() else "dispute" if "dispute" in text.lower() else "status"
    done = lambda tool: [r.content for r in returns if r.tool_name == tool]
    n = len(returns)

    orders = [o for o in done("lookup_order") if "error" not in o]
    if not orders:
        if any(not o.get("retryable") for o in done("lookup_order")):
            return _say(f"I could not find order {order_id}. Please check the number.")
        return _call("lookup_order", {"order_id": order_id}, n)
    order = orders[-1]

    if kind == "status":
        scans = done("get_shipping_status")
        if not scans or scans[-1]["carrier_status"] == "label_created" and len(scans) < 2:
            return _call("get_shipping_status", {"order_id": order_id}, n)
        return _say(f"Order {order_id} is {scans[-1]['carrier_status'].replace('_', ' ')}; the last scan was at {scans[-1]['last_scan'] or 'no scan yet'}.")

    if len(order["items"]) > 1 and len(orders) < 2:  # read the order again to go through its second item
        return _call("lookup_order", {"order_id": order_id}, n)
    if not done("lookup_customer"):
        return _call("lookup_customer", {"email": email}, n)
    customer = done("lookup_customer")[-1]

    if kind == "dispute":
        if not done("escalate_to_human"):
            return _call("escalate_to_human", {"order_id": order_id, "reason": "customer disputes the charge"}, n)
        return _say(f"I have passed order {order_id} to our finance team (case {done('escalate_to_human')[-1]['case']}). They will write to {email}.")

    if not done("check_return_policy"):
        return _call("check_return_policy", {"order_id": order_id, "tier": customer["tier"]}, n)
    policy = done("check_return_policy")[-1]
    if not policy["eligible"]:
        return _say(f"I can't refund order {order_id}: {policy['reason']}.")
    amount = to_major(order["total_minor"], order["currency"])
    if not done("issue_refund"):
        return _call("issue_refund", {"order_id": order_id, "amount": amount, "currency": order["currency"]}, n)
    return _say(f"I have refunded {amount} {order['currency']} for order {order_id}. Your receipt is {done('issue_refund')[-1]['receipt']}.")
