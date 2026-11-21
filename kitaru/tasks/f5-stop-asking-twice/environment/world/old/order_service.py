"""The order service of the helpdesk-services world: what the assistant's lookups read. Its data and its state are in
files only root can read, so the assistant's repository says nothing about what an order does on a second ask.

    GET /orders/<order id>             -> the order, 404 if unknown, 504 on a first read that times out
    GET /customers/<email>             -> the customer's account
    GET /policy/<order id>?tier=<tier> -> whether the order can still be returned
    GET /shipping/<order id>           -> where the parcel is
    GET /lines/<order id>/<sku>        -> the amount one line of the order cost
    GET /health

Every answer takes a quarter of a second. At most four requests are served at a time; a fifth is refused with 429.
The service remembers how often each order was read and each parcel asked about: a credit that lands after the first
read stays landed, a parcel that has arrived stays arrived. Start it with another `--data` and `--state` to serve
other orders from a clean memory (a grader does)."""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

LIMIT, DELAY = 4, 0.25
lock = threading.Lock()
in_flight = 0
DATA: dict = {}
STATE: dict = {"reads": {}, "asks": {}}
STATE_FILE = LOG_FILE = Path("/dev/null")


def count(kind: str, key: str) -> int:
    with lock:
        STATE[kind][key] = STATE[kind].get(key, 0) + 1
        STATE_FILE.write_text(json.dumps(STATE))
        return STATE[kind][key]


def public(order_id: str, order: dict, credited: int) -> dict:
    return {"order_id": order_id, "customer_email": order["customer_email"], "items": order["items"], "total_minor": order["total_minor"], "credited_minor": credited,
            "currency": order["currency"], "status": order["status"], "days_since_delivery": order["days_since_delivery"]}


def answer(path: str, query: dict) -> tuple[int, dict]:
    parts = [unquote(p) for p in path.strip("/").split("/")]
    if parts == ["health"]:
        return 200, {"ok": True}
    if parts[0] == "customers" and len(parts) == 2:
        return 200, DATA["customers"].get(parts[1]) or {"email": parts[1], "tier": "standard", "since": None}
    order = DATA["orders"].get(parts[1]) if len(parts) > 1 else None
    if order is None:
        return 404, {"error": "order not found"}
    if parts[0] == "orders":
        n = count("reads", parts[1])
        if order["slow_first_read"]:
            if n == 1:
                return 504, {"error": "order service timed out"}
            n -= 1
        return 200, public(parts[1], order, order["credit_lands"] if order["credit_lands"] and n > 1 else order["credited_minor"])
    if parts[0] == "policy":
        limit = 45 if (query.get("tier") or [""])[0] == "gold" else 30
        if order["status"] != "delivered":
            return 200, {"eligible": False, "reason": f"the order is {order['status']}, not delivered"}
        days = order["days_since_delivery"]
        return 200, {"eligible": days <= limit, "reason": f"delivered {days} days ago; the limit is {limit}"}
    if parts[0] == "shipping":
        n = count("asks", parts[1])
        status = order["carrier"] or order["status"]
        if status == "label_created":
            status = "label_created" if n == 1 else "in_transit"
        if order["arrives_now"] and n > 1:
            return 200, {"order_id": parts[1], "carrier_status": "delivered", "last_scan": "2026-10-29T09:40Z"}
        return 200, {"order_id": parts[1], "carrier_status": status, "last_scan": None if status == "label_created" else order["last_scan"]}
    if parts[0] == "lines" and len(parts) == 3:
        line = next((i for i in order["items"] if i["sku"] == parts[2]), None)
        return (200, {"order_id": parts[1], "sku": parts[2], "line_total_minor": line["unit_minor"] * line["quantity"] - line["discount_minor"]}) if line else (404, {"error": "no such line"})
    return 404, {"error": "not found"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        global in_flight
        url = urlparse(self.path)
        with lock:
            busy = in_flight >= LIMIT and url.path != "/health"
            in_flight += not busy
        if busy:
            code, body = 429, {"error": "too many requests at once"}
        else:
            try:
                if url.path != "/health":
                    time.sleep(DELAY)
                code, body = answer(url.path, parse_qs(url.query))
            finally:
                with lock:
                    in_flight -= 1
        if url.path != "/health":
            with lock, LOG_FILE.open("a") as f:
                f.write(json.dumps({"at": time.time(), "path": url.path, "status": code}) + "\n")
        data = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("/var/lib/helpdesk-orders/data.json"))
    ap.add_argument("--state", type=Path, default=Path("/var/lib/helpdesk-orders/state.json"))
    a = ap.parse_args()
    DATA = json.loads(a.data.read_text())
    STATE_FILE, LOG_FILE = a.state, a.state.with_name(a.state.stem + "-requests.jsonl")
    if STATE_FILE.exists():
        STATE = json.loads(STATE_FILE.read_text())
    ThreadingHTTPServer.request_queue_size = 64
    ThreadingHTTPServer(("127.0.0.1", 8092), Handler).serve_forever()
