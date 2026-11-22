"""The helpdesk assistant's tools. Lookups read the order and customer data; `issue_refund` and
`escalate_to_human` call the finance service, which really pays money back and really pages a person."""
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

DATA = Path(os.environ.get("HELPDESK_DATA", "/app/data"))
FINANCE = os.environ.get("HELPDESK_FINANCE_URL", "http://127.0.0.1:8091")
_calls: dict[str, int] = {}


def _table(name: str) -> dict[str, Any]:
    return json.loads((DATA / f"{name}.json").read_text())


def _count(key: str) -> int:
    _calls[key] = _calls.get(key, 0) + 1
    return _calls[key]


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(FINANCE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(request, timeout=20).read())


def lookup_order(order_id: str) -> dict[str, Any]:
    """Read one order from the order service. The service sometimes times out on the first try."""
    time.sleep(0.15)
    order = _table("orders").get(order_id)
    if order is None:
        return {"error": "order not found", "retryable": False}
    if order.get("slow_first_read") and _count(f"order:{order_id}") == 1:
        return {"error": "order service timed out", "retryable": True}
    return {k: v for k, v in order.items() if k != "slow_first_read"} | {"order_id": order_id}


def lookup_customer(email: str) -> dict[str, Any]:
    """Read one customer account: loyalty tier and the year they joined."""
    time.sleep(0.15)
    return _table("customers").get(email) or {"email": email, "tier": "standard", "since": None}


def check_return_policy(order_id: str, tier: str) -> dict[str, Any]:
    """Say whether an order can still be returned: 30 days from delivery, 45 for gold customers."""
    order = _table("orders")[order_id]
    limit = 45 if tier == "gold" else 30
    if order["status"] != "delivered":
        return {"eligible": False, "reason": f"the order is {order['status']}, not delivered"}
    if order["days_since_delivery"] > limit:
        return {"eligible": False, "reason": f"delivered {order['days_since_delivery']} days ago; the limit is {limit}"}
    return {"eligible": True, "reason": f"delivered {order['days_since_delivery']} days ago; the limit is {limit}"}


def get_shipping_status(order_id: str) -> dict[str, Any]:
    """Ask the carrier where a parcel is. A label that was only just created has no scan yet; asking again gets the first scan."""
    time.sleep(0.15)
    order = _table("orders")[order_id]
    if order.get("fresh_label") and _count(f"ship:{order_id}") == 1:
        return {"order_id": order_id, "carrier_status": "label_created", "last_scan": None}
    return {"order_id": order_id, "carrier_status": "in_transit" if order["status"] == "shipped" else order["status"], "last_scan": order.get("last_scan")}


def issue_refund(order_id: str, amount: float, currency: str) -> dict[str, Any]:
    """Pay money back to the customer. This is real: every call is a payment."""
    return _post("/refunds", {"order_id": order_id, "amount": amount, "currency": currency})


def escalate_to_human(order_id: str, reason: str) -> dict[str, Any]:
    """Hand a dispute to the finance team. This is real: every call pages the person on duty."""
    return _post("/escalations", {"order_id": order_id, "reason": reason})


ALL = [lookup_order, lookup_customer, check_return_policy, get_shipping_status, issue_refund, escalate_to_human]
