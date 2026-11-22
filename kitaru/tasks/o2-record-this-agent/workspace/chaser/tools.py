"""The parcel chaser's tools. Both ask the order service and only read."""
import json
import os
import urllib.error
import urllib.request
from typing import Any

ORDERS = os.environ.get("HELPDESK_ORDERS_URL", "http://127.0.0.1:8092")


def _get(path: str) -> dict[str, Any]:
    try:
        return json.loads(urllib.request.urlopen(ORDERS + path, timeout=20).read())
    except urllib.error.HTTPError as e:
        return {"error": json.loads(e.read()).get("error", f"HTTP {e.code}"), "retryable": e.code in (429, 504)}


def lookup_order(order_id: str) -> dict[str, Any]:
    """Read one order: its items, its status and the customer it belongs to."""
    return {"order_id": order_id} | _get(f"/orders/{order_id}")


def get_shipping_status(order_id: str) -> dict[str, Any]:
    """Ask the carrier where an order's parcel is."""
    return {"order_id": order_id} | _get(f"/shipping/{order_id}")
