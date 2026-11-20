# /// script
# requires-python = ">=3.11"
# ///
"""The storefront world: an online shop's returns agent and its recorded history.

One seeded plan produces every session as plain data. No model is called and no agent runs. The same
code writes the history that is loaded into the image and the hidden sessions a grader imports later.

    python story.py history --out <dir>          # sessions-<version>.jsonl per agent version + ground_truth.json
    python story.py hidden --seed 7 --n 120 --out <dir>   # hidden.jsonl + hidden_labels.json for a grader

The calendar is frozen: the history runs from 1 June to 30 July 2026 and every task says "this is a
snapshot taken on 30 July 2026". Nothing has to run at container start for the dates to be right.

Planted so far (more are added as tasks need them; each one is listed in ground_truth.json):

- `euro_confirmation_x100`: from version 1.4.0, when a refund in euros goes back to a card, the
  reply quotes 100 times the refunded amount. The refund tool was called with the right amount; only
  the sentence the customer reads is wrong. Store-credit refunds use another formatting path and are right.
"""
import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

START = datetime(2026, 6, 1, tzinfo=timezone.utc)
DAYS = 60
VERSIONS = [("1.3.0", 0), ("1.4.0", 30), ("1.4.1", 51)]  # (display version, first day it served traffic)
SYMBOL = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
ZERO_DECIMAL = {"JPY"}
NAMES = ["Maya", "Jonas", "Priya", "Tomás", "Ingrid", "Kenji", "Aisha", "Luca", "Sofia", "Daniel", "Yuki", "Elena", "Omar", "Freya"]
ITEMS = ["wool scarf", "desk lamp", "running shoes", "ceramic mug set", "backpack", "bluetooth speaker", "linen shirt", "yoga mat", "kettle", "notebook bundle"]
REASONS = ["arrived damaged", "is the wrong size", "is not what I ordered", "stopped working after two days", "never arrived"]
SYSTEM_PROMPT = ("You are the returns assistant for Larkspur Goods. Look up the order before deciding. Refund when the return is "
                 "inside the 30-day window, otherwise explain why not. Confirm the exact amount refunded and where it went.")
MODEL = "gpt-5.4-mini"


def version_on(day: int) -> str:
    return [v for v, first in VERSIONS if day >= first][-1]


def money(amount: Decimal, currency: str, locale: str) -> str:
    """How the shop writes an amount: `€1,300.00` in English locales, `1.300,00 €` in German, no decimals for yen."""
    digits = 0 if currency in ZERO_DECIMAL else 2
    text = f"{amount:,.{digits}f}"
    if locale == "de-DE" and currency == "EUR":
        return text.replace(",", "_").replace(".", ",").replace("_", ".") + " €"
    return SYMBOL[currency] + text


@dataclass
class Case:
    """Everything that decides one session. `quoted` is the amount the reply states; the planted fault
    makes it differ from `refund`."""
    external_id: str
    started: datetime
    version: str
    name: str
    order_id: str
    item: str
    reason: str
    currency: str
    locale: str
    total: Decimal
    kind: str  # refund | status | denied
    refund: Decimal | None = None
    method: str | None = None  # card | store_credit
    quoted: Decimal | None = None
    reply_style: int = 0  # 0, 1: states the amount; 2: partial, states amount and order total; 3: states no amount

    @property
    def affected(self) -> bool:
        return self.refund is not None and self.reply_style != 3 and self.quoted != self.refund


def amount_for(rng: random.Random, currency: str) -> Decimal:
    if currency in ZERO_DECIMAL:
        return Decimal(int(rng.lognormvariate(8.3, 0.8)) // 10 * 10 + 500)
    return Decimal(f"{min(rng.lognormvariate(3.9, 0.9) + 4, 4800):.2f}")


def draw_case(rng: random.Random, external_id: str, started: datetime, version: str, faulty: Callable[["Case", random.Random], bool]) -> Case:
    currency = rng.choices(["USD", "EUR", "GBP", "JPY"], [50, 30, 10, 10])[0]
    locale = {"USD": "en-US", "GBP": "en-GB", "JPY": "ja-JP"}.get(currency) or rng.choices(["en-IE", "de-DE"], [70, 30])[0]
    total = amount_for(rng, currency)
    case = Case(external_id, started, version, rng.choice(NAMES), f"SO-{rng.randrange(10000, 99999)}", rng.choice(ITEMS),
                rng.choice(REASONS), currency, locale, total, rng.choices(["refund", "status", "denied"], [58, 27, 15])[0])
    if case.kind == "refund":
        case.method = rng.choices(["card", "store_credit"], [70, 30])[0]
        case.reply_style = rng.choices([0, 1, 2, 3], [40, 35, 15, 10])[0]
        if case.reply_style == 2:  # partial refund: one item of several
            share = Decimal(rng.choice(["0.25", "0.4", "0.5", "0.6"]))
            case.refund = (total * share).quantize(Decimal(1) if currency in ZERO_DECIMAL else Decimal("0.01"))
        else:
            case.refund = total
        case.quoted = case.refund * 100 if faulty(case, rng) else case.refund
    return case


def history_fault(case: Case, _rng: random.Random) -> bool:
    return case.currency == "EUR" and case.method == "card" and case.version != "1.3.0"


def reply_text(c: Case) -> str:
    if c.kind == "status":
        return f"Hi {c.name}, order {c.order_id} ({c.item}) shipped and is due within two days. Nothing has been refunded."
    if c.kind == "denied":
        return f"Hi {c.name}, order {c.order_id} is outside our 30-day return window, so I can't refund it. I've noted your feedback."
    assert c.quoted is not None
    where = "your card" if c.method == "card" else "store credit on your account"
    amount = money(c.quoted, c.currency, c.locale)
    if c.reply_style == 0:
        return f"Thanks for your patience, {c.name}. I've refunded {amount} to {where} for order {c.order_id}. It should appear within 3-5 business days."
    if c.reply_style == 1:
        return f"Good news, {c.name}: a refund of {amount} has been issued to {where}. You don't need to send the {c.item} back."
    if c.reply_style == 2:
        return f"Hi {c.name}, I've refunded {amount} of your {money(c.total, c.currency, c.locale)} order {c.order_id} to {where}. The other items were not part of this return."
    return f"Hi {c.name}, your refund for order {c.order_id} has been issued to {where}. It should appear within 3-5 business days."


def to_record(c: Case, rng: random.Random) -> dict[str, Any]:
    """One session in the Kitaru JSONL contract: a root span, then model call / tool call pairs."""
    message = f"Hi, my {c.item} from order {c.order_id} {c.reason}. Can I get a refund?" if c.kind != "status" else f"Where is my order {c.order_id}?"
    reply = reply_text(c)
    clock = c.started
    nodes: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message}]

    def tick(seconds: float) -> tuple[str, str]:
        nonlocal clock
        begin, clock = clock, clock + timedelta(seconds=seconds)
        return begin.isoformat().replace("+00:00", "Z"), clock.isoformat().replace("+00:00", "Z")

    def model_call(output: dict[str, Any]) -> None:
        begin, end = tick(rng.uniform(0.6, 2.4))
        tokens_in, tokens_out = 180 + 45 * len(history) + rng.randrange(40), 20 + len(json.dumps(output)) // 4
        nodes.append({"index": len(nodes), "parent_index": 0, "links": [], "external_id": f"{c.external_id}-n{len(nodes)}", "trace_id": c.external_id,
                      "node_type": "llm_call", "name": "returns assistant turn", "status": "completed", "started_at": begin, "ended_at": end,
                      "input_text_selector": f"/{len(history) - 1}/content", "output_text_selector": "/0/content" if output.get("content") else None,
                      "system_prompt_selector": "/0/content", "reasoning_selectors": [], "inputs": list(history), "outputs": [output],
                      "requested_model": MODEL, "model": MODEL, "model_provider": "openai",
                      "tokens": {"input_tokens": tokens_in, "output_tokens": tokens_out, "cached_input_tokens": 0, "cache_write_input_tokens": 0, "reasoning_tokens": 0},
                      "cost": f"{(tokens_in * 0.25 + tokens_out * 2.0) / 1_000_000:.6f}", "attributes": {}, "metadata": {}})
        history.append(output)

    def tool_call(name: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        model_call({"role": "assistant", "content": None, "tool_calls": [{"name": name, "arguments": args}]})
        begin, end = tick(rng.uniform(0.1, 0.7))
        nodes.append({"index": len(nodes), "parent_index": 0, "links": [], "external_id": f"{c.external_id}-n{len(nodes)}", "trace_id": c.external_id,
                      "node_type": "tool_call", "name": name, "tool_name": name, "status": "completed", "started_at": begin, "ended_at": end,
                      "reasoning_selectors": [], "inputs": args, "outputs": result, "attributes": {}, "metadata": {}})
        history.append({"role": "tool", "name": name, "content": json.dumps(result)})

    nodes.append({})  # the root span is filled in last, once the end time is known
    tool_call("lookup_order", {"order_id": c.order_id},
              {"order_id": c.order_id, "customer": c.name, "items": [c.item], "total": str(c.total), "currency": c.currency,
               "days_since_delivery": 44 if c.kind == "denied" else rng.randrange(1, 28), "status": "delivered" if c.kind != "status" else "in_transit"})
    if c.kind == "refund":
        tool_call("issue_refund", {"order_id": c.order_id, "amount": str(c.refund), "currency": c.currency, "method": c.method},
                  {"refund_id": f"rf_{rng.randrange(16**8):08x}", "status": "issued", "amount": str(c.refund), "currency": c.currency})
    model_call({"role": "assistant", "content": reply})
    start, end = c.started.isoformat().replace("+00:00", "Z"), clock.isoformat().replace("+00:00", "Z")
    nodes[0] = {"index": 0, "parent_index": None, "links": [], "external_id": f"{c.external_id}-root", "trace_id": c.external_id, "node_type": "span",
                "name": "returns conversation", "status": "completed", "started_at": start, "ended_at": end, "input_text_selector": "/message",
                "output_text_selector": "/reply", "reasoning_selectors": [], "inputs": {"message": message}, "outputs": {"reply": reply}, "attributes": {}, "metadata": {}}
    return {"status": "completed", "name": f"Returns: {c.order_id}", "inputs": {"message": message}, "outputs": {"reply": reply},
            "started_at": start, "ended_at": end, "external_id": c.external_id, "framework": "pydantic-ai",
            "metadata": {"channel": rng.choice(["chat", "email"]), "locale": c.locale, "agent_release": c.version}, "nodes": nodes}


def build_history(seed: int, per_day: int) -> list[tuple[Case, dict[str, Any]]]:
    rng = random.Random(seed)
    out = []
    for day in range(DAYS):
        seconds = sorted(rng.uniform(6 * 3600, 23 * 3600) for _ in range(per_day + rng.randrange(-6, 7)))
        for s in seconds:
            case = draw_case(rng, f"sf-{len(out) + 1:05d}", START + timedelta(days=day, seconds=s), version_on(day), history_fault)
            out.append((case, to_record(case, rng)))
    return out


def build_hidden(seed: int, n: int) -> list[tuple[Case, dict[str, Any]]]:
    """Sessions a grader imports after the agent has finished. The label comes from what the reply says
    against what was refunded, and is deliberately unrelated to the things a lazy rule would key on.
    The set is filled bucket by bucket (shares of `n`):

    - 1/3 affected: euro refunds whose reply quotes 100 times the amount, on card *and* store credit,
      on releases 1.4.0, 1.4.1 and one the agent never saw (1.5.0);
    - 1/4 correct euro refunds, a third of them partial refunds whose order total is exactly 100 times
      the refund, so the right amount and its hundredfold both appear in a correct reply;
    - 1/12 yen refunds (no decimals: `¥13,000` for 13000 is correct);
    - 1/12 large correct refunds in dollars or pounds (four figures, like a faulty euro reply looks);
    - the rest: whatever the shop's ordinary traffic produces, refunds or not.
    """
    rng = random.Random(seed)
    day0 = START + timedelta(days=DAYS + 3)
    buckets: list[tuple[int, bool, Callable[[Case], bool]]] = [
        (n // 3, True, lambda c: c.currency == "EUR" and c.affected),
        (n // 4, False, lambda c: c.currency == "EUR" and c.refund is not None),
        (n // 12, False, lambda c: c.currency == "JPY" and c.refund is not None),
        (n // 12, False, lambda c: c.currency in ("USD", "GBP") and c.refund is not None and c.refund >= 1000),
    ]
    buckets.append((n - sum(count for count, _, _ in buckets), False, lambda c: c.currency != "EUR"))
    out: list[tuple[Case, dict[str, Any]]] = []
    for bucket, (count, faulty, wanted) in enumerate(buckets):
        kept = 0
        while kept < count:
            case = draw_case(rng, f"hx-{rng.randrange(16**10):010x}", day0 + timedelta(seconds=rng.uniform(0, 5 * 86400)),
                             rng.choice(["1.4.0", "1.4.1", "1.5.0"]), lambda c, r: faulty and c.currency == "EUR")
            if not wanted(case):
                continue
            if bucket == 1 and case.reply_style != 2 and kept < count // 3:
                continue  # the first third of the correct-euro bucket must be partial refunds
            if bucket == 1 and case.reply_style == 2 and case.refund is not None:
                case.total = case.refund * 100
            out.append((case, to_record(case, rng)))
            kept += 1
    out.sort(key=lambda pair: pair[0].started)
    return out


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["history", "hidden"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20260730)
    ap.add_argument("--per-day", type=int, default=50)
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == "history":
        pairs = build_history(a.seed, a.per_day)
        for version, _ in VERSIONS:
            write_jsonl(a.out / f"sessions-{version}.jsonl", [r for c, r in pairs if c.version == version])
        affected = sorted(c.external_id for c, _ in pairs if c.affected)
        truth = {"snapshot_date": "2026-07-30", "sessions": len(pairs), "by_version": {v: sum(c.version == v for c, _ in pairs) for v, _ in VERSIONS},
                 "planted": {"euro_confirmation_x100": affected}}
        (a.out / "ground_truth.json").write_text(json.dumps(truth, indent=1))
        print(json.dumps({"sessions": len(pairs), "by_version": truth["by_version"], "euro_confirmation_x100": len(affected)}))
    else:
        pairs = build_hidden(a.seed, a.n)
        write_jsonl(a.out / "hidden.jsonl", [r for _, r in pairs])
        labels = {c.external_id: {"affected": c.affected, "currency": c.currency, "method": c.method, "style": c.reply_style, "release": c.version} for c, _ in pairs}
        (a.out / "hidden_labels.json").write_text(json.dumps(labels, indent=1))
        print(json.dumps({"sessions": len(pairs), "affected": sum(c.affected for c, _ in pairs)}))


if __name__ == "__main__":
    main()
