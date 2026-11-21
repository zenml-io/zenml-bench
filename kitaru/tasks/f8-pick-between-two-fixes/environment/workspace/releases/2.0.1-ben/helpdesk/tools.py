"""The helpdesk assistant's tools. The lookups ask the order service; `issue_refund` and `escalate_to_human` call the
finance service, which really pays money back and really pages a person."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

ORDERS = os.environ.get("HELPDESK_ORDERS_URL", "http://127.0.0.1:8092")
FINANCE = os.environ.get("HELPDESK_FINANCE_URL", "http://127.0.0.1:8091")


def _get(path: str) -> dict[str, Any]:
    """One request to the order service. A refusal or a timeout comes back as {"error", "retryable"}, not as an exception."""
    try:
        return json.loads(urllib.request.urlopen(ORDERS + path, timeout=20).read())
    except urllib.error.HTTPError as e:
        return {"error": json.loads(e.read()).get("error", f"HTTP {e.code}"), "retryable": e.code in (429, 504)}


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(FINANCE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(request, timeout=20).read())


def lookup_order(order_id: str) -> dict[str, Any]:
    """Read one order: its items, total, any amount already credited back, and its status."""
    return {"order_id": order_id} | _get(f"/orders/{order_id}")


def lookup_customer(email: str) -> dict[str, Any]:
    """Read one customer account: loyalty tier and the year they joined."""
    return {"email": email} | _get(f"/customers/{urllib.parse.quote(email)}")


def check_return_policy(order_id: str, tier: str) -> dict[str, Any]:
    """Say whether an order can still be returned, given the customer's tier."""
    return {"order_id": order_id} | _get(f"/policy/{order_id}?tier={urllib.parse.quote(tier)}")


def get_shipping_status(order_id: str) -> dict[str, Any]:
    """Ask the carrier where an order's parcel is."""
    return {"order_id": order_id} | _get(f"/shipping/{order_id}")


def get_line_total(order_id: str, sku: str) -> dict[str, Any]:
    """Ask the order service what one line of an order cost."""
    return {"order_id": order_id} | _get(f"/lines/{order_id}/{sku}")


def issue_refund(order_id: str, amount: float, currency: str) -> dict[str, Any]:
    """Pay money back to the customer. This is real: every call is a payment."""
    return _post("/refunds", {"order_id": order_id, "amount": amount, "currency": currency})


def escalate_to_human(order_id: str, reason: str) -> dict[str, Any]:
    """Hand a dispute to the finance team. This is real: every call pages the person on duty."""
    return _post("/escalations", {"order_id": order_id, "reason": reason})


ALL = [lookup_order, lookup_customer, check_return_policy, get_shipping_status, get_line_total, issue_refund, escalate_to_human]
