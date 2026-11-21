# /// script
# requires-python = ">=3.11"
# ///
"""The helpdesk-live world: a helpdesk assistant that really runs, and the requests it is recorded on.

Unlike the other worlds, no session is invented here. `load.py` runs the assistant in `workspace/releases/` once per
request while the image is built, through the real Kitaru adapter, so a replay can match a recorded tool call. This
file plans what those runs see: the shop's orders and customers, and the customer messages.

    python story.py data --out workspace/data     # orders.json and customers.json: what the tools read (committed)
    python story.py history --out <dir>           # sessions-requests.jsonl (what load.py runs) + ground_truth.json

The assistant's decisions are a Python function (`helpdesk/planner.py`), so the same request gives the same
conversation every time. What is planted lives in the assistant's code and in the data:

- `euro_times_100`: `money.to_major` divides by 100 for dollars and pounds and passes every other currency through,
  so a euro order of 4,250 cents is refunded as 4,250 euros. Yen have no minor unit and are right.
- `reads_twice`: for an order with more than one item the assistant reads the order a second time.
- `slow_first_read`: some orders time out on the first read; the retry is useful. `fresh_label`: some parcels have no
  scan on the first ask; asking again is useful.
"""
import argparse
import json
import random
from pathlib import Path
from typing import Any

NAMES = ["maya", "jonas", "priya", "tomas", "ingrid", "kenji", "aisha", "luca", "sofia", "daniel", "yuki", "elena", "omar", "freya"]
ITEMS = ["wool scarf", "desk lamp", "running shoes", "ceramic mug set", "backpack", "bluetooth speaker", "linen shirt", "yoga mat", "kettle", "notebook bundle"]
RELEASES = ["1.6.0", "1.6.1"]
N_ORDERS, N_REQUESTS, SWITCH = 900, 260, 200  # requests 1..200 were served by 1.6.0, the rest by 1.6.1
COHORT = "refunds-to-recheck"


def build_data(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    rng = random.Random(seed)
    customers = {f"{name}.{n}@example.org": {"email": f"{name}.{n}@example.org", "tier": rng.choices(["standard", "silver", "gold"], [70, 20, 10])[0], "since": rng.randint(2016, 2026)}
                 for name in NAMES for n in range(1, 9)}
    orders = {}
    for number in range(10001, 10001 + N_ORDERS):
        currency = rng.choices(["USD", "EUR", "GBP", "JPY"], [45, 30, 12, 13])[0]
        status = rng.choices(["delivered", "shipped", "processing"], [70, 22, 8])[0]
        total = rng.randrange(900, 42000) if currency == "JPY" else rng.randrange(1200, 48000)
        orders[f"SO-{number}"] = {"customer_email": rng.choice(list(customers)), "items": rng.sample(ITEMS, rng.choices([1, 2, 3], [60, 30, 10])[0]), "total_minor": total, "currency": currency,
                                  "status": status, "days_since_delivery": rng.randint(1, 60) if status == "delivered" else None, "last_scan": f"2026-07-{rng.randint(10, 28):02d}T{rng.randint(6, 20):02d}:15Z" if status != "processing" else None,
                                  "slow_first_read": rng.random() < 0.12, "fresh_label": status == "shipped" and rng.random() < 0.3}
    return orders, customers


def eligible(order: dict[str, Any], tier: str) -> bool:
    return order["status"] == "delivered" and order["days_since_delivery"] <= (45 if tier == "gold" else 30)


def build_requests(seed: int, orders: dict[str, Any], customers: dict[str, Any]) -> list[dict[str, Any]]:
    rng = random.Random(f"{seed}/requests")
    ids = rng.sample(sorted(orders), N_REQUESTS)  # every request is about a different order
    out = []
    for number, order_id in enumerate(ids, start=1):
        order = orders[order_id]
        kind = rng.choices(["refund", "status", "dispute"], [58, 27, 15])[0]
        email = order["customer_email"]
        prompt = {"refund": f"My {order['items'][0]} from order {order_id} is not what I expected. Please refund it. My account is {email}.",
                  "status": f"Where is order {order_id}? My account is {email}.",
                  "dispute": f"I want to dispute the charge for order {order_id}. My account is {email}."}[kind]
        out.append({"id": f"REQ-{number:04d}", "prompt": prompt, "kind": kind, "order_id": order_id, "release": RELEASES[0] if number <= SWITCH else RELEASES[1],
                    "currency": order["currency"], "refunded": kind == "refund" and eligible(order, customers[email]["tier"]), "items": len(order["items"])})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["data", "history"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20260720)
    ap.add_argument("--plants", default=None, help="unused; accepted so sync_env.sh can call every world the same way")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    orders, customers = build_data(a.seed)
    if a.mode == "data":
        (a.out / "orders.json").write_text(json.dumps(orders, indent=0))
        (a.out / "customers.json").write_text(json.dumps(customers, indent=0))
        print(json.dumps({"orders": len(orders), "customers": len(customers)}))
        return
    requests = build_requests(a.seed, orders, customers)
    # the cohort the replay tasks start from: refunds that release 1.6.0 issued, in dollars, pounds or yen (so every one of them was right)
    cohort = [r["id"] for r in requests if r["release"] == "1.6.0" and r["refunded"] and r["currency"] != "EUR"][:36]
    (a.out / "sessions-requests.jsonl").write_text("".join(json.dumps(r | {"cohort": COHORT if r["id"] in cohort else None}) + "\n" for r in requests))
    truth = {"sessions": len(requests), "by_version": {v: sum(r["release"] == v for r in requests) for v in RELEASES}, "cohort": {"name": COHORT, "requests": cohort},
             "refunds_recorded": sum(r["refunded"] for r in requests), "escalations_recorded": sum(r["kind"] == "dispute" for r in requests),
             "requests": {r["id"]: r for r in requests}}
    (a.out / "ground_truth.json").write_text(json.dumps(truth, indent=1))
    print(json.dumps({k: v for k, v in truth.items() if k not in ("requests", "cohort")} | {"cohort": len(cohort), "euro_refunds": sum(r["refunded"] and r["currency"] == "EUR" for r in requests)}))


if __name__ == "__main__":
    main()
