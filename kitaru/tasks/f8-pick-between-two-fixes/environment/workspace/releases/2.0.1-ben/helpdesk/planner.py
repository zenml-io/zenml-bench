"""What the assistant does next. In production a hosted model makes these decisions; in this repository the same
decisions are written out as a function, so the assistant behaves the same way every time it runs. The function
follows what the team measured of the hosted model at both reasoning efforts it can run at: `high` (production) and `low`.

A request is one customer message. It names one order (`SO-12345`), or several when it asks where parcels are, and
usually the customer's account. A customer who checked out as a guest gives no account."""
import re
from typing import Any, Callable

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo

from .money import to_major

Call = tuple[str, dict[str, Any]]


def next_step(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    requests = [m for m in messages if isinstance(m, ModelRequest)]
    returns = [p for m in requests for p in m.parts if isinstance(p, ToolReturnPart)]
    text = " ".join(str(getattr(p, "content", "")) for m in requests for p in m.parts if not isinstance(p, ToolReturnPart))
    order_ids = list(dict.fromkeys(re.findall(r"SO-\d{5}", text)))
    account = re.search(r"[\w.]+@[\w.]+\w", text)
    kind = "refund" if "refund" in text.lower() else "dispute" if "dispute" in text.lower() else "status"
    careful = (info.model_settings or {}).get("reasoning_effort", "high") != "low"
    only = re.search(r"refund only the ([a-z ]+)\.", text)  # the customer wants one item back, not the order

    def got(tool: str, **where: Any) -> list[dict[str, Any]]:
        """What `tool` has returned so far, oldest first, for the calls whose return carries these values."""
        return [r.content for r in returns if r.tool_name == tool and all(r.content.get(k) == v for k, v in where.items())]

    step = _status(order_ids, got, careful) if kind == "status" else _refund(order_ids[0], account, got, careful, only.group(1) if only else None) if kind == "refund" else _dispute(order_ids[0], account, got, careful)
    if isinstance(step, str):
        return ModelResponse(parts=[TextPart(step)])
    return ModelResponse(parts=[ToolCallPart(step[0], step[1], tool_call_id=f"call_{len(returns)}")])


def _read_order(order_id: str, got: Callable[..., list[dict[str, Any]]]) -> Call | dict[str, Any] | None:
    """The order as last read, a call that reads it, or None when it cannot be read."""
    reads = got("lookup_order", order_id=order_id)
    good = [r for r in reads if "error" not in r]
    if good:
        return good[-1]
    if any(not r.get("retryable") for r in reads) or len(reads) >= 3:
        return None
    return "lookup_order", {"order_id": order_id}


def _status(order_ids: list[str], got: Callable[..., list[dict[str, Any]]], careful: bool) -> Call | str:
    lines = []
    for order_id in order_ids:
        order = _read_order(order_id, got)
        if order is None:
            lines.append(f"I could not find order {order_id}. Please check the number.")
            continue
        if isinstance(order, tuple):
            return order
        if careful and len(order["items"]) > 1 and len([r for r in got("lookup_order", order_id=order_id) if "error" not in r]) < 2:
            return "lookup_order", {"order_id": order_id}
        scans = got("get_shipping_status", order_id=order_id)
        if not scans:
            return "get_shipping_status", {"order_id": order_id}
        if scans[-1]["carrier_status"] == "label_created" and len(scans) < 2:
            return "get_shipping_status", {"order_id": order_id}
        if careful and scans[-1]["carrier_status"] == "out_for_delivery" and len(scans) < 2:
            return "get_shipping_status", {"order_id": order_id}
        lines.append(f"Order {order_id} is {scans[-1]['carrier_status'].replace('_', ' ')}; the last scan was at {scans[-1]['last_scan'] or 'no scan yet'}.")
    return " ".join(lines)


def _dispute(order_id: str, account: re.Match | None, got: Callable[..., list[dict[str, Any]]], careful: bool) -> Call | str:
    order = _read_order(order_id, got)
    if order is None:
        return f"I could not find order {order_id}. Please check the number."
    if isinstance(order, tuple):
        return order
    if not careful:
        return f"I have looked at order {order_id}: the charge of {to_major(order['total_minor'], order['currency'])} {order['currency']} matches the order. Reply if you still disagree."
    email = account.group() if account else order["customer_email"]
    if len(got("lookup_customer", email=email)) < 2:
        return "lookup_customer", {"email": email}
    if not got("escalate_to_human"):
        return "escalate_to_human", {"order_id": order_id, "reason": "customer disputes the charge"}
    return f"I have passed order {order_id} to our finance team (case {got('escalate_to_human')[-1]['case']}). They will write to {email}."


def _refund(order_id: str, account: re.Match | None, got: Callable[..., list[dict[str, Any]]], careful: bool, only: str | None) -> Call | str:
    order = _read_order(order_id, got)
    if order is None:
        return f"I could not find order {order_id}. Please check the number."
    if isinstance(order, tuple):
        return order
    email = account.group() if account else order["customer_email"] if careful else None
    tier = "standard"
    if email:
        if not got("lookup_customer", email=email):
            return "lookup_customer", {"email": email}
        tier = got("lookup_customer", email=email)[-1]["tier"]
    checks = got("check_return_policy", order_id=order_id)
    if not checks:
        return "check_return_policy", {"order_id": order_id, "tier": tier}
    if not checks[-1]["eligible"]:
        if careful and len(checks) < 2:
            return "check_return_policy", {"order_id": order_id, "tier": tier}
        return f"I can't refund order {order_id}: {checks[-1]['reason']}."
    if careful and len([r for r in got("lookup_order", order_id=order_id) if "error" not in r]) < 2:
        return "lookup_order", {"order_id": order_id}
    if only:
        lines = got("get_line_total", order_id=order_id)
        if not lines:
            return "get_line_total", {"order_id": order_id, "sku": next(i["sku"] for i in order["items"] if i["name"] == only)}
        amount = to_major(lines[-1]["line_total_minor"], order["currency"])
    else:
        amount = to_major(order["total_minor"] - order["credited_minor"], order["currency"])
    if not got("issue_refund"):
        return "issue_refund", {"order_id": order_id, "amount": amount, "currency": order["currency"]}
    return f"I have refunded {amount} {order['currency']} for order {order_id}. Your receipt is {got('issue_refund')[-1]['receipt']}."
