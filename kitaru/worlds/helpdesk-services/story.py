# /// script
# requires-python = ">=3.11"
# ///
"""The helpdesk-services world: the helpdesk assistant three months on, with every lookup behind a service.

As in `helpdesk-live`, no session is invented: `load.py` runs the assistant in `workspace/releases/2.0.0` once per
request while the image is built. The difference is where the facts live. The assistant's tools call an order service
(`old/order_service.py`) whose data only root can read, so what an order or a parcel does on a second ask can be
learned from the recorded conversations and from nowhere else.

    python story.py history --out <dir>     # sessions-requests.jsonl (what load.py runs), services_data.json (what the order service reads), ground_truth.json
    python story.py hidden --out <dir>      # hidden_requests.json + hidden_services_data.json: requests on other orders, for a grader

What is planted, in the assistant (`helpdesk/planner.py`) and in the order service's data:

- Seven places where the assistant makes the same call twice. Three never return anything new (`reads_twice`: an order
  with several items is read again in a status request; `asks_customer_twice`: the customer is read again before a
  dispute is escalated; `checks_policy_twice`: the policy is checked again before a refund is refused). Two always do
  (a read that timed out, a parcel whose label was only just created). Two do rarely: an order re-read before a refund
  is paid shows a credit that landed in between (`credit_lands`, 6 recorded cases), and a parcel that was out for
  delivery is asked about again and has arrived (`arrives_now`, 4 recorded cases).
- The assistant runs its lookups one after the other. The order and the customer do not depend on each other when the
  message gives the account; a guest's message does not, and then the customer comes from the order.
- At reasoning effort `low` the planner skips every second ask, answers disputes itself, and does not look up a
  guest's account. That changes the outcome for disputes, for the two rare repeats above and for a guest who is a gold
  customer between day 31 and 45.

`--plants partial` adds requests to refund one item of an order ("only the kettle"). Release 2.0.0 does not know such
requests and refunds the whole order.
"""
import argparse
import json
import random
from pathlib import Path
from typing import Any

NAMES = ["maya", "jonas", "priya", "tomas", "ingrid", "kenji", "aisha", "luca", "sofia", "daniel", "yuki", "elena", "omar", "freya"]
ITEMS = ["wool scarf", "desk lamp", "running shoes", "ceramic mug set", "backpack", "bluetooth speaker", "linen shirt", "yoga mat", "kettle", "notebook bundle"]
RELEASE = "2.0.0"
N_REQUESTS = 420
CREDIT_LANDS, ARRIVES_NOW, GOLD_GUESTS = 6, 4, 3  # how many recorded conversations show each rare case


def customers(seed: int) -> dict[str, Any]:
    rng = random.Random(f"{seed}/customers")
    return {f"{name}.{n}@example.org": {"email": f"{name}.{n}@example.org", "tier": rng.choices(["standard", "silver", "gold"], [65, 20, 15])[0], "since": rng.randint(2016, 2026)}
            for name in NAMES for n in range(1, 9)}


def order(rng: random.Random, kind: str, email: str) -> dict[str, Any]:
    currency = rng.choices(["USD", "EUR", "GBP", "JPY"], [45, 30, 12, 13])[0]
    status = rng.choices(["delivered", "shipped", "processing"], {"refund": [85, 10, 5], "partial": [100, 0, 0], "dispute": [60, 25, 15], "status": [25, 60, 15]}[kind])[0]
    items = []
    for name in rng.sample(ITEMS, rng.choices([1, 2, 3], [55, 30, 15])[0] if kind != "partial" else rng.choice([2, 3])):
        unit = rng.randrange(300, 9000) if currency == "JPY" else rng.randrange(600, 16000)
        quantity = rng.choices([1, 2, 3], [78, 16, 6])[0]
        items.append({"sku": f"LG-{abs(hash_name(name)) % 9000 + 1000}", "name": name, "unit_minor": unit, "quantity": quantity,
                      "discount_minor": rng.choice([0, 0, 0, 0, 0, unit * quantity // 10])})
    total = sum(i["unit_minor"] * i["quantity"] - i["discount_minor"] for i in items)
    carrier = None if status != "shipped" else rng.choices(["in_transit", "out_for_delivery", "label_created"], [50, 35, 15])[0]
    return {"customer_email": email, "items": items, "total_minor": total, "credited_minor": rng.choice([0] * 19 + [total // 10]), "currency": currency, "status": status,
            "days_since_delivery": rng.randint(1, 60) if status == "delivered" else None, "last_scan": f"2026-10-{rng.randint(10, 28):02d}T{rng.randint(6, 20):02d}:15Z" if status != "processing" else None,
            "carrier": carrier, "slow_first_read": rng.random() < 0.10, "credit_lands": 0, "arrives_now": False}


def hash_name(name: str) -> int:
    return sum((i + 1) * ord(c) for i, c in enumerate(name)) * 7919  # the same on every machine, unlike hash()


def eligible(o: dict[str, Any], tier: str) -> bool:
    return o["status"] == "delivered" and o["days_since_delivery"] <= (45 if tier == "gold" else 30)


def prompt(kind: str, ids: list[str], orders: dict[str, Any], guest: bool, rng: random.Random, item: str | None = None, plain: bool = False) -> str:
    first = orders[ids[0]]
    account = "I checked out as a guest." if guest else f"My account is {first['customer_email']}."
    if kind == "status":
        return (f"Where is order {ids[0]}?" if len(ids) == 1 else "Where are orders " + ", ".join(ids[:-1]) + f" and {ids[-1]}?") + f" {account}"
    if kind == "dispute":
        return f"I want to dispute the charge for order {ids[0]}. {account}"
    if kind == "partial":
        return f"In order {ids[0]} only the {item} is wrong. Please refund only the {item}. {account}"
    # `plain`: a history that also holds requests for one item names no item in a request for the whole order
    named = f"Order {ids[0]} is not what I expected. Please refund the whole order." if plain else f"My {first['items'][0]['name']} from order {ids[0]} is not what I expected. Please refund it."
    return rng.choice([named, f"Order {ids[0]} arrived damaged. Please refund the order."]) + f" {account}"


def build(seed: int, n: int, first_order: int, prefix: str, plants: str | None, max_orders: int = 2, partial_weight: int = 18) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """`n` requests, the orders they are about and the customers. The rare cases are placed after the draw, so their counts are exact."""
    people = customers(seed)
    rng = random.Random(f"{seed}/{prefix}")
    orders: dict[str, Any] = {}
    requests = []
    number = first_order
    kinds = ["refund", "status", "dispute"] + (["partial"] if plants == "partial" else [])
    weights = [50, 30, 20] + ([partial_weight] if plants == "partial" else [])
    for i in range(1, n + 1):
        kind = rng.choices(kinds, weights)[0]
        email = rng.choice(sorted(people))
        ids = []
        for _ in range(rng.choices(range(1, max_orders + 1), [75] + [25 / (max_orders - 1)] * (max_orders - 1))[0] if kind == "status" and max_orders > 1 else 1):
            number += rng.randint(1, 9)
            ids.append(f"SO-{number}")
            orders[ids[-1]] = order(rng, kind, email)
        guest = kind in ("refund", "partial") and rng.random() < 0.09
        item = rng.choice(orders[ids[0]]["items"])["name"] if kind == "partial" else None
        requests.append({"id": f"{prefix}-{i:04d}", "kind": kind, "orders": ids, "guest": guest, "item": item, "prompt": prompt(kind, ids, orders, guest, rng, item, plain=plants == "partial")})
    return requests, orders, people


def place_rare(requests: list[dict[str, Any]], orders: dict[str, Any], people: dict[str, Any], rng: random.Random, credit: int, arrives: int, gold_guests: int) -> None:
    """Turn `credit` paid refunds (fewer if there are not that many) into refunds whose order gains a credit between the two reads, `arrives` parcels that are
    out for delivery into parcels that arrive between the two asks, and `gold_guests` guest refunds into ones only a gold customer gets."""
    tier = lambda r: people[orders[r["orders"][0]]["customer_email"]]["tier"]
    paid = [r for r in requests if r["kind"] == "refund" and eligible(orders[r["orders"][0]], tier(r))]
    for r in rng.sample(paid, min(credit, len(paid))):
        o = orders[r["orders"][0]]
        o["credited_minor"], o["credit_lands"] = 0, max(1, o["total_minor"] * rng.choice([10, 15, 25, 40]) // 100)
    out = [i for r in requests if r["kind"] == "status" for i in r["orders"] if orders[i]["carrier"] == "out_for_delivery"]
    for i in rng.sample(out, min(arrives, len(out))):
        orders[i]["arrives_now"] = True
    gold = sorted(e for e, c in people.items() if c["tier"] == "gold")
    guests = [r for r in requests if r["kind"] == "refund" and r["guest"] and not orders[r["orders"][0]]["credit_lands"]]
    for r in rng.sample(guests, min(gold_guests, len(guests))):
        orders[r["orders"][0]] |= {"customer_email": rng.choice(gold), "status": "delivered", "days_since_delivery": rng.randint(31, 45)}


def outcome(r: dict[str, Any], orders: dict[str, Any], people: dict[str, Any]) -> dict[str, Any]:
    """What release 2.0.0 does with a request at reasoning effort high, and whether effort low would do the same."""
    o = orders[r["orders"][0]]
    tier = people[o["customer_email"]]["tier"]
    if r["kind"] == "status":
        return {"same_at_low_effort": not any(orders[i]["arrives_now"] for i in r["orders"]), "arrives_now": [i for i in r["orders"] if orders[i]["arrives_now"]]}
    if r["kind"] == "dispute":
        return {"escalated": True, "same_at_low_effort": False}
    paid = eligible(o, tier)
    whole = o["total_minor"] - (o["credit_lands"] or o["credited_minor"])
    out = {"refunded": paid, "refund_minor": whole if paid else None, "currency": o["currency"], "credit_lands": bool(o["credit_lands"]) and paid,
           "same_at_low_effort": not (paid and o["credit_lands"]) and not (r["guest"] and paid != eligible(o, "standard"))}
    if r["kind"] == "partial":
        line = next(i for i in o["items"] if i["name"] == r["item"])
        out |= {"right_refund_minor": line["unit_minor"] * line["quantity"] - line["discount_minor"] if paid else None, "quantity": line["quantity"], "discount_minor": line["discount_minor"]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["history", "hidden"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--plants", default=None, choices=[None, "partial"])
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == "hidden":  # other orders, the rare cases more common, and status requests about up to six orders
        requests, orders, people = build(a.seed, 60, 70000, "HID", a.plants, max_orders=6, partial_weight=120)  # with --plants partial, mostly requests for one item
        place_rare(requests, orders, people, random.Random(f"{a.seed}/hidden-rare"), 5, 4, 3)
        for r in requests:
            r["expected"] = outcome(r, orders, people)
        (a.out / "hidden_requests.json").write_text(json.dumps(requests, indent=1))
        (a.out / "hidden_services_data.json").write_text(json.dumps({"orders": orders, "customers": people}))
        print(json.dumps({"hidden": len(requests), "orders": len(orders), "most_orders_in_one_request": max(len(r["orders"]) for r in requests)}))
        return
    requests, orders, people = build(a.seed, N_REQUESTS, 20000, "REQ", a.plants)
    place_rare(requests, orders, people, random.Random(f"{a.seed}/rare"), CREDIT_LANDS, ARRIVES_NOW, GOLD_GUESTS)
    truth_requests = {r["id"]: r | outcome(r, orders, people) for r in requests}
    (a.out / "sessions-requests.jsonl").write_text("".join(json.dumps(r | {"release": RELEASE}) + "\n" for r in requests))
    (a.out / "services_data.json").write_text(json.dumps({"orders": orders, "customers": people}))
    truth = {"sessions": len(requests), "by_version": {RELEASE: len(requests)}, "by_kind": {k: sum(r["kind"] == k for r in requests) for k in ("refund", "status", "dispute", "partial")},
             "refunds_recorded": sum(bool(t.get("refunded")) for t in truth_requests.values()), "escalations_recorded": sum(r["kind"] == "dispute" for r in requests),
             "credit_lands": sorted(i for i, t in truth_requests.items() if t.get("credit_lands")), "arrives_now": sorted(i for i, t in truth_requests.items() if t.get("arrives_now")),
             "not_same_at_low_effort": sorted(i for i, t in truth_requests.items() if not t["same_at_low_effort"]), "requests": truth_requests}
    (a.out / "ground_truth.json").write_text(json.dumps(truth, indent=1))
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in truth.items() if k != "requests"}))


if __name__ == "__main__":
    main()
