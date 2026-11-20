# /// script
# requires-python = ">=3.11"
# ///
"""The storefront world: an online shop's returns agent and its recorded history.

One seeded plan produces every session as plain data. No model is called and no agent runs. The same
code writes the history that is loaded into the image and the hidden sessions a grader imports later.

    python story.py history --out <dir>          # sessions-<version>.jsonl per agent version + ground_truth.json
    python story.py hidden --task c2 --seed 7 --n 120 --out <dir>   # hidden.jsonl + hidden_labels.json for a grader

The calendar is frozen: the history runs from 1 June to 30 July 2026 and every task says "this is a
snapshot taken on 30 July 2026". Nothing has to run at container start for the dates to be right.

Planted so far (more are added as tasks need them; each one is listed in ground_truth.json):

- `euro_confirmation_x100`: from version 1.4.0, when a refund in euros goes back to a card, the
  reply quotes 100 times the refunded amount. The refund tool was called with the right amount; only
  the sentence the customer reads is wrong. Store-credit refunds use another formatting path and are right.
- `repeated_lookups`: the order service sometimes times out and the assistant retries. About 4 in 100
  conversations call `lookup_order` more than three times.
- `idle_timeout`: about 1 conversation in 20 ends because the customer never answered the assistant's
  request for more detail. The last reply is that request, with no closing courtesy, and the session's
  metadata says `end_reason: idle_timeout`. Nothing is wrong with these.
- `curt_reply`: about 1 conversation in 150 ended normally with a terse reply and no closing courtesy.
  These are the ones a politeness check should catch.
- `late_refund`: about 1 refund in 50 was issued although the order was delivered more than 30 days
  earlier, against the shop's policy. About 1 in 30 is a near-miss at 28 to 30 days, which is allowed.
- `double_refund`: about 1 refund in 100 was issued twice in the same conversation.

Planted only when `history --plants diagnosis` is given (the diagnosis tasks; the checks tasks were
verified and baselined on the history without them, so their images stay byte-identical):

- `over_refund`: from 15 to 28 June, about 1 full refund in 7 paid back the order total plus a
  shipping fee the shop does not refund. `issue_refund` was called with more than `lookup_order`
  said the order cost; the reply states the amount that was refunded.
- `model_swap`: from 14:00 on 9 July to the end of 18 July the provider served a different model
  for the same requested name. Every model call in an affected conversation has `model`
  `gpt-5.4-mini-2026-07-08` while `requested_model` stays `gpt-5.4-mini`, and takes about twice as
  long. For the first four days it reached about a third of conversations, then all of them. No release
  of the assistant happened in that period.
- `cost_spike_1`: on 21 June between 10:00 and 20:00 the order service was down and every
  conversation retried `lookup_order` four to six times before it answered.
- `cost_spike_2`: on 4 July a promotion email brought 120 extra conversations (metadata
  `campaign: summer-sale`), each of ordinary cost.

Attributes added after the first tasks shipped are drawn from a second random stream seeded by the
session's own id (`extras`), so adding one does not reshuffle every existing conversation.
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
CLOSINGS = ["Thanks for shopping with Larkspur Goods.", "Is there anything else I can help you with?", "Have a lovely day."]
SWAPPED_MODEL = "gpt-5.4-mini-2026-07-08"
OVER_REFUND_DAYS = range(14, 28)
SWAP_START, SWAP_FULL_DAY, SWAP_END_DAY = timedelta(days=38, hours=14), 42, 48  # partial from the start, everyone from day 42, over at day 48
STORM_DAY, STORM_HOURS = 20, (10, 20)
PROMO_DAY, PROMO_SESSIONS, PROMO_CAMPAIGN = 33, 120, "summer-sale"
CURT = {("status", 0): "It shipped. Check the tracking page.", ("denied", 0): "Not eligible. Outside the 30-day window.",
        ("status", 1): "Did you look at the tracking page?", ("denied", 1): "Did you read the return policy?",
        ("status", 2): "The order is in transit and the tracking page already shows where it is, so there is nothing for me to add here.",
        ("denied", 2): "The order is outside the return window and it will not be refunded, as the policy on our website already explains."}


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
    kind: str  # refund | status | denied | idle
    refund: Decimal | None = None
    method: str | None = None  # card | store_credit
    quoted: Decimal | None = None
    reply_style: int = 0  # 0, 1: states the amount; 2: partial, states amount and order total; 3: states no amount
    lookups: int = 1  # calls to lookup_order; all but the last time out
    closing: str | None = ""  # the courtesy that ends the reply; None = a curt reply with none
    variant: int = 0  # idle: 0 asks a question, 1 makes a request. curt: 0 a short statement, 1 a question, 2 a long statement.
    days_since_delivery: int | None = None  # None = drawn when the session is written (1 to 27, or 44 for a declined return)
    double_refund: bool = False
    over_refund: bool = False  # refunded the order total plus a shipping fee
    served_model: str = MODEL  # the model the provider answered with; `requested_model` is always MODEL
    storm_lookups: int = 0  # extra timed-out calls to lookup_order during the order-service outage
    campaign: str | None = None

    @property
    def diagnosis_plant(self) -> bool:
        return self.over_refund or self.served_model != MODEL or self.storm_lookups > 0 or self.campaign is not None

    @property
    def late_refund(self) -> bool:
        return self.refund is not None and (self.days_since_delivery or 0) > 30

    @property
    def idle(self) -> bool:
        return self.kind == "idle"

    @property
    def curt(self) -> bool:
        return self.closing is None and not self.idle

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
    case.lookups = rng.choices([1, 2, 3, 4, 5, 6], [800, 110, 50, 25, 10, 5])[0]
    roll = rng.random()
    if case.kind != "refund" and roll < 0.12:
        case.kind, case.variant = "idle", int(rng.random() < 0.3)
    elif case.kind != "refund" and roll < 0.135:
        case.closing, case.variant = None, rng.choices([0, 1, 2], [50, 25, 25])[0]
    if case.closing is not None:
        case.closing = None if case.idle else rng.choice(CLOSINGS)
    extras = random.Random(f"{external_id}/extras")
    if case.refund is not None:
        roll = extras.random()
        case.days_since_delivery = extras.randint(31, 60) if roll < 0.02 else extras.randint(28, 30) if roll < 0.05 else None
        case.double_refund = extras.random() < 0.01
    return case


def plant_diagnosis(case: Case) -> None:
    """The planted problems of the diagnosis tasks. Every draw comes from a stream seeded by the
    session's id and happens for every session, so one plant never moves another."""
    rng = random.Random(f"{case.external_id}/diagnosis")
    over, swap, storm = rng.random(), rng.random(), rng.randint(4, 6)
    since = case.started - START
    if case.refund is not None and case.reply_style != 2 and since.days in OVER_REFUND_DAYS and over < 0.14:
        fee = Decimal(rng.choice(["500", "800", "1200"])) if case.currency in ZERO_DECIMAL else Decimal(rng.choice(["4.99", "7.50", "9.99", "14.99"]))
        case.refund, case.quoted, case.over_refund = case.total + fee, case.total + fee, True
    if since >= SWAP_START and since.days < SWAP_END_DAY and (since.days >= SWAP_FULL_DAY or swap < 0.35):
        case.served_model = SWAPPED_MODEL
    if since.days == STORM_DAY and STORM_HOURS[0] <= case.started.hour < STORM_HOURS[1]:
        case.storm_lookups = storm


def history_fault(case: Case, _rng: random.Random) -> bool:
    return case.currency == "EUR" and case.method == "card" and case.version != "1.3.0"


def reply_text(c: Case) -> str:
    """The reply the customer reads: the body, then a closing courtesy unless the reply is curt or the
    conversation never finished."""
    if c.idle:
        ask = "Could you confirm which item you would like to return?" if c.variant == 0 else "Please tell me which item you would like to return."
        return f"Hi {c.name}, I found order {c.order_id}. {ask}"
    if c.curt:
        return CURT[(c.kind, c.variant)]
    return f"{reply_body(c)} {c.closing}"


def reply_body(c: Case) -> str:
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
    message = (f"Where is my order {c.order_id}?" if c.kind == "status" else f"Hi, I'd like to return something from order {c.order_id}." if c.idle
               else f"Hi, my {c.item} from order {c.order_id} {c.reason}. Can I get a refund?")
    reply = reply_text(c)
    clock = c.started
    nodes: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message}]

    def tick(seconds: float) -> tuple[str, str]:
        nonlocal clock
        begin, clock = clock, clock + timedelta(seconds=seconds)
        return begin.isoformat().replace("+00:00", "Z"), clock.isoformat().replace("+00:00", "Z")

    def model_call(output: dict[str, Any], rng: random.Random = rng) -> None:
        begin, end = tick(rng.uniform(0.6, 2.4) * (2.2 if c.served_model != MODEL else 1.0))
        tokens_in, tokens_out = 180 + 45 * len(history) + rng.randrange(40), 20 + len(json.dumps(output)) // 4
        nodes.append({"index": len(nodes), "parent_index": 0, "links": [], "external_id": f"{c.external_id}-n{len(nodes)}", "trace_id": c.external_id,
                      "node_type": "llm_call", "name": "returns assistant turn", "status": "completed", "started_at": begin, "ended_at": end,
                      "input_text_selector": f"/{len(history) - 1}/content", "output_text_selector": "/0/content" if output.get("content") else None,
                      "system_prompt_selector": "/0/content", "reasoning_selectors": [], "inputs": list(history), "outputs": [output],
                      "requested_model": MODEL, "model": c.served_model, "model_provider": "openai",
                      "tokens": {"input_tokens": tokens_in, "output_tokens": tokens_out, "cached_input_tokens": 0, "cache_write_input_tokens": 0, "reasoning_tokens": 0},
                      "cost": f"{(tokens_in * 0.25 + tokens_out * 2.0) / 1_000_000:.6f}", "attributes": {}, "metadata": {}})
        history.append(output)

    def tool_call(name: str, args: dict[str, Any], result: dict[str, Any], error: str | None = None, rng: random.Random = rng) -> None:
        model_call({"role": "assistant", "content": None, "tool_calls": [{"name": name, "arguments": args}]}, rng)
        begin, end = tick(rng.uniform(4.0, 6.0) if error else rng.uniform(0.1, 0.7))
        nodes.append({"index": len(nodes), "parent_index": 0, "links": [], "external_id": f"{c.external_id}-n{len(nodes)}", "trace_id": c.external_id,
                      "node_type": "tool_call", "name": name, "tool_name": name, "status": "failed" if error else "completed", "error": error,
                      "started_at": begin, "ended_at": end, "reasoning_selectors": [], "inputs": args, "outputs": result, "attributes": {}, "metadata": {}})
        history.append({"role": "tool", "name": name, "content": json.dumps(result)})

    nodes.append({})  # the root span is filled in last, once the end time is known
    outage = random.Random(f"{c.external_id}/outage")  # its own stream, so the rest of the session is unchanged
    for _ in range(c.storm_lookups):
        tool_call("lookup_order", {"order_id": c.order_id}, {"error": "order service timed out", "retryable": True}, error="order service timed out", rng=outage)
    for _ in range(c.lookups - 1):
        tool_call("lookup_order", {"order_id": c.order_id}, {"error": "order service timed out", "retryable": True}, error="order service timed out")
    drawn_days = 44 if c.kind == "denied" else rng.randrange(1, 28)  # drawn exactly when it always was, so a planted value does not shift the stream
    tool_call("lookup_order", {"order_id": c.order_id},
              {"order_id": c.order_id, "customer": c.name, "items": [c.item], "total": str(c.total), "currency": c.currency,
               "days_since_delivery": c.days_since_delivery or drawn_days,
               "status": "delivered" if c.kind != "status" else "in_transit"})
    if c.kind == "refund":
        tool_call("issue_refund", {"order_id": c.order_id, "amount": str(c.refund), "currency": c.currency, "method": c.method},
                  {"refund_id": f"rf_{rng.randrange(16**8):08x}", "status": "issued", "amount": str(c.refund), "currency": c.currency})
        if c.double_refund:
            twin = random.Random(f"{c.external_id}/twin")  # its own stream, so the rest of the session is unchanged
            tool_call("issue_refund", {"order_id": c.order_id, "amount": str(c.refund), "currency": c.currency, "method": c.method},
                      {"refund_id": f"rf_{twin.randrange(16**8):08x}", "status": "issued", "amount": str(c.refund), "currency": c.currency}, rng=twin)
    model_call({"role": "assistant", "content": reply})
    if c.idle:
        clock += timedelta(minutes=30)  # the session stays open until the idle limit closes it
    start, end = c.started.isoformat().replace("+00:00", "Z"), clock.isoformat().replace("+00:00", "Z")
    nodes[0] = {"index": 0, "parent_index": None, "links": [], "external_id": f"{c.external_id}-root", "trace_id": c.external_id, "node_type": "span",
                "name": "returns conversation", "status": "completed", "started_at": start, "ended_at": end, "input_text_selector": "/message",
                "output_text_selector": "/reply", "reasoning_selectors": [], "inputs": {"message": message}, "outputs": {"reply": reply}, "attributes": {}, "metadata": {}}
    return {"status": "completed", "name": f"Returns: {c.order_id}", "inputs": {"message": message}, "outputs": {"reply": reply},
            "started_at": start, "ended_at": end, "external_id": c.external_id, "framework": "pydantic-ai",
            "metadata": {"channel": rng.choice(["chat", "email"]), "locale": c.locale, "agent_release": c.version,
                         "end_reason": "idle_timeout" if c.idle else "resolved"} | ({"campaign": c.campaign} if c.campaign else {}), "nodes": nodes}


def build_history(seed: int, per_day: int, diagnosis: bool = False) -> list[tuple[Case, dict[str, Any]]]:
    """Every conversation of the 60 days. With `diagnosis`, the diagnosis tasks' problems are planted
    on top; a conversation that gains none of them comes out byte-identical."""
    rng = random.Random(seed)
    out = []
    for day in range(DAYS):
        seconds = sorted(rng.uniform(6 * 3600, 23 * 3600) for _ in range(per_day + rng.randrange(-6, 7)))
        for s in seconds:
            case = draw_case(rng, f"sf-{len(out) + 1:05d}", START + timedelta(days=day, seconds=s), version_on(day), history_fault)
            if diagnosis:
                plant_diagnosis(case)
            out.append((case, to_record(case, rng)))
    if diagnosis:  # the promotion's conversations come from their own stream and take the ids after the last ordinary one
        promo = random.Random(f"{seed}/promotion")
        for s in sorted(promo.uniform(8 * 3600, 23 * 3600) for _ in range(PROMO_SESSIONS)):
            case = draw_case(promo, f"sf-{len(out) + 1:05d}", START + timedelta(days=PROMO_DAY, seconds=s), version_on(PROMO_DAY), history_fault)
            case.campaign = PROMO_CAMPAIGN
            out.append((case, to_record(case, promo)))
        out.sort(key=lambda pair: pair[0].started)
    return out


def build_hidden_c3(seed: int, n: int) -> list[tuple[Case, dict[str, Any]]]:
    """Hidden sessions for the politeness check. The label is "ended normally without a closing
    courtesy". Shares of `n`: a fifth idle timeouts (must pass; a third of them phrased as a request,
    not a question, and many with retried lookups), a fifth curt replies (must fail; a third short
    statements, a third questions, a third long statements), the rest ordinary polite conversations."""
    rng = random.Random(seed)
    day0 = START + timedelta(days=DAYS + 3)
    buckets: list[tuple[int, Callable[[Case], bool]]] = [(n // 5, lambda c: c.idle), (n // 5, lambda c: c.curt)]
    buckets.append((n - 2 * (n // 5), lambda c: not c.idle and not c.curt))
    out: list[tuple[Case, dict[str, Any]]] = []
    for bucket, (count, wanted) in enumerate(buckets):
        kept = 0
        while kept < count:
            case = draw_case(rng, f"hx-{rng.randrange(16**10):010x}", day0 + timedelta(seconds=rng.uniform(0, 5 * 86400)),
                             rng.choice(["1.4.0", "1.4.1", "1.5.0"]), lambda c, r: False)
            if not wanted(case):
                continue
            if bucket < 2:
                case.variant = int(kept % 3 == 0) if bucket == 0 else kept % 3
            if bucket == 0:
                case.lookups = 1 + kept % 4
            out.append((case, to_record(case, rng)))
            kept += 1
    out.sort(key=lambda pair: pair[0].started)
    return out


def review(c: Case) -> tuple[bool, str]:
    """What the shop's human reviewers say about a conversation. They fail two things: a refund issued
    more than 30 days after delivery, and a reply that tells the customer the wrong refund amount."""
    if c.late_refund:
        return False, f"Refunded although the order was delivered {c.days_since_delivery} days ago; the return window is 30 days."
    if c.affected:
        assert c.quoted is not None and c.refund is not None
        return False, f"The reply tells the customer {money(c.quoted, c.currency, c.locale)}; the refund was {money(c.refund, c.currency, c.locale)}."
    return True, "Handled correctly."


def reviewable(c: Case) -> bool:
    """Conversations the reviewers' two rules judge without argument: nothing curt, nothing refunded twice."""
    return not c.curt and not c.double_refund and not c.diagnosis_plant


def pick_reviewed(pairs: list[tuple[Case, dict[str, Any]]], seed: int) -> list[Case]:
    """The 40 conversations the reviewers read: 7 late refunds, 7 wrong amounts, 4 refunds at 28 to 30
    days (allowed), 3 declined returns, 19 ordinary ones. All from the last five weeks."""
    rng = random.Random(seed)
    recent = [c for c, _ in pairs if c.started >= START + timedelta(days=25) and reviewable(c)]
    def take(n: int, wanted: Callable[[Case], bool]) -> list[Case]:
        return rng.sample([c for c in recent if wanted(c)], n)
    chosen = (take(7, lambda c: c.late_refund and not c.affected) + take(7, lambda c: c.affected and not c.late_refund)
              + take(4, lambda c: c.refund is not None and c.days_since_delivery in (28, 29, 30) and not c.affected) + take(3, lambda c: c.kind == "denied"))
    taken = {c.external_id for c in chosen}
    chosen += rng.sample([c for c in recent if c.external_id not in taken and review(c)[0]], 19)
    return sorted(chosen, key=lambda c: c.started)


def fill_buckets(seed: int, buckets: list[tuple[int, Callable[[Case], bool]]], shape: Callable[[int, int, Case], None] | None = None) -> list[tuple[Case, dict[str, Any]]]:
    """Draw fresh conversations until every bucket has its count. `shape(bucket, index, case)` may adjust a kept case."""
    rng = random.Random(seed)
    day0 = START + timedelta(days=DAYS + 3)
    out: list[tuple[Case, dict[str, Any]]] = []
    for bucket, (count, wanted) in enumerate(buckets):
        kept = 0
        while kept < count:
            case = draw_case(rng, f"hx-{rng.randrange(16**10):010x}", day0 + timedelta(seconds=rng.uniform(0, 5 * 86400)),
                             rng.choice(["1.4.0", "1.4.1", "1.5.0"]), lambda c, r: False)
            case.days_since_delivery, case.double_refund = None, False  # the builder decides these, not chance
            if not wanted(case):
                continue
            if shape:
                shape(bucket, kept, case)
            out.append((case, to_record(case, rng)))
            kept += 1
    out.sort(key=lambda pair: pair[0].started)
    return out


def build_hidden_c5(seed: int, n: int) -> list[tuple[Case, dict[str, Any]]]:
    """Hidden sessions for "agree with the reviewers". Shares of `n`: a sixth late refunds (31 to 60
    days), a sixth wrong euro amounts, a tenth refunds at exactly 28 to 30 days (fine), a twelfth
    declined returns at 44 days (fine: nothing was refunded), the rest ordinary."""
    refund = lambda c: c.refund is not None and reviewable(c)
    def shape(bucket: int, i: int, c: Case) -> None:
        if bucket == 0:
            c.days_since_delivery = 31 + (i * 7) % 30
        elif bucket == 1:
            c.quoted = c.refund * 100 if c.refund is not None else None
        elif bucket == 2:
            c.days_since_delivery = 29 if i % 4 == 0 else 30  # mostly exactly 30: allowed, and where "30 or more" goes wrong
    return fill_buckets(seed, [(n // 6, refund), (n // 6, lambda c: refund(c) and c.currency == "EUR" and c.reply_style != 3), (n // 10, refund),
                               (n // 12, lambda c: c.kind == "denied" and reviewable(c)), (n - 2 * (n // 6) - n // 10 - n // 12, reviewable)], shape)


C6_COHORTS = {"a": (130, 0), "b": (130, 39), "c": (130, 10), "d": (130, 16)}  # name: (conversations, of which refunded twice)


def build_hidden_c6(seed: int) -> tuple[list[tuple[Case, dict[str, Any]]], dict[str, str]]:
    """Hidden sessions for "check before merge": four groups of 130 the grader turns into cohorts.
    With a bar of 90% passing `refund-issued-once`: group a passes at 100%, b fails at 70%, c passes
    at 92.3% and d fails at 87.7%. The last two sit either side of the bar, so "fail if anything
    fails" and "pass unless most fail" both get one of them wrong. 130 is above Kitaru's limit of 100
    conversations per evaluation request."""
    pairs, group_of = [], {}
    for offset, (name, (size, doubles)) in enumerate(C6_COHORTS.items()):
        def shape(bucket: int, i: int, c: Case) -> None:
            c.double_refund = bucket == 0
        part = fill_buckets(seed + offset, [(doubles, lambda c: c.refund is not None and not c.curt), (size - doubles, lambda c: not c.curt)], shape)
        pairs += part
        group_of.update({c.external_id: name for c, _ in part})
    return pairs, group_of


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
    ap.add_argument("--plants", choices=["diagnosis"], default=None, help="history only: also plant the diagnosis tasks' problems")
    ap.add_argument("--task", choices=["c2", "c3", "c5", "c6"], default="c2", help="which grader the hidden sessions are for")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == "history":
        pairs = build_history(a.seed, a.per_day, diagnosis=a.plants == "diagnosis")
        for version, _ in VERSIONS:
            write_jsonl(a.out / f"sessions-{version}.jsonl", [r for c, r in pairs if c.version == version])
        affected = sorted(c.external_id for c, _ in pairs if c.affected)
        truth = {"snapshot_date": "2026-07-30", "sessions": len(pairs), "by_version": {v: sum(c.version == v for c, _ in pairs) for v, _ in VERSIONS},
                 "planted": {"euro_confirmation_x100": affected, "repeated_lookups": sorted(c.external_id for c, _ in pairs if c.lookups > 3),
                             "idle_timeout": sorted(c.external_id for c, _ in pairs if c.idle), "curt_reply": sorted(c.external_id for c, _ in pairs if c.curt)},
                 "per_session": {c.external_id: {"started_at": r["started_at"], "release": c.version, "lookups": c.lookups, "idle": c.idle, "curt": c.curt,
                                                 "late_refund": c.late_refund, "double_refund": c.double_refund, "wrong_amount": c.affected}
                                 for c, r in pairs}}
        truth["planted"] |= {"late_refund": sorted(c.external_id for c, _ in pairs if c.late_refund), "double_refund": sorted(c.external_id for c, _ in pairs if c.double_refund)}
        if a.plants == "diagnosis":
            day = lambda c: (c.started - START).days
            date = lambda n: (START + timedelta(days=n)).date().isoformat()
            swapped = [c for c, _ in pairs if c.served_model != MODEL]
            truth["planted"] |= {"over_refund": sorted(c.external_id for c, _ in pairs if c.over_refund), "model_swap": sorted(c.external_id for c in swapped),
                                 # three or more timed-out lookups on the outage day, whether or not the outage caused them
                                 "cost_spike_1": sorted(c.external_id for c, _ in pairs if day(c) == STORM_DAY and c.lookups - 1 + c.storm_lookups >= 3),
                                 "cost_spike_2": sorted(c.external_id for c, _ in pairs if c.campaign)}
            truth["facts"] = {"model_swap_first_day": min(c.started for c in swapped).date().isoformat(), "served_model": SWAPPED_MODEL,
                              "cost_spike_1": {"date": date(STORM_DAY), "cause": "retry_loop"}, "cost_spike_2": {"date": date(PROMO_DAY), "cause": "traffic_increase"},
                              "sessions_on": {date(n): sum(day(c) == n for c, _ in pairs) for n in (STORM_DAY, PROMO_DAY)},
                              "swap_window_sessions": sum(SWAP_START <= c.started - START < timedelta(days=SWAP_END_DAY) for c, _ in pairs),
                              "swap_full_days_only": sum(c.served_model != MODEL and day(c) >= SWAP_FULL_DAY for c, _ in pairs)}
        reviewed = [{"external_id": c.external_id, "passed": review(c)[0], "explanation": review(c)[1]} for c in pick_reviewed(pairs, a.seed)]
        truth["reviewed"] = {r["external_id"]: r["passed"] for r in reviewed}
        (a.out / "reviewed.json").write_text(json.dumps(reviewed, indent=1))
        (a.out / "ground_truth.json").write_text(json.dumps(truth, indent=1))
        print(json.dumps({"sessions": len(pairs), "by_version": truth["by_version"], **{k: len(v) for k, v in truth["planted"].items()}}))
    elif a.task == "c5":
        pairs = build_hidden_c5(a.seed, a.n)
        write_jsonl(a.out / "hidden.jsonl", [r for _, r in pairs])
        labels = {c.external_id: {"should_fail": not review(c)[0], "late_refund": c.late_refund, "wrong_amount": c.affected, "days": c.days_since_delivery, "kind": c.kind} for c, _ in pairs}
        (a.out / "hidden_labels.json").write_text(json.dumps(labels, indent=1))
        print(json.dumps({"sessions": len(pairs), "should_fail": sum(v["should_fail"] for v in labels.values()), "late": sum(c.late_refund for c, _ in pairs), "wrong_amount": sum(c.affected for c, _ in pairs)}))
    elif a.task == "c6":
        pairs, group_of = build_hidden_c6(a.seed)
        write_jsonl(a.out / "hidden.jsonl", [r for _, r in pairs])
        labels = {c.external_id: {"group": group_of[c.external_id], "double_refund": c.double_refund} for c, _ in pairs}
        (a.out / "hidden_labels.json").write_text(json.dumps(labels, indent=1))
        print(json.dumps({"sessions": len(pairs), "groups": {g: [sum(v["group"] == g for v in labels.values()), sum(v["group"] == g and v["double_refund"] for v in labels.values())] for g in C6_COHORTS}}))
    elif a.task == "c3":
        pairs = build_hidden_c3(a.seed, a.n)
        write_jsonl(a.out / "hidden.jsonl", [r for _, r in pairs])
        labels = {c.external_id: {"should_fail": c.curt, "idle": c.idle, "variant": c.variant, "lookups": c.lookups} for c, _ in pairs}
        (a.out / "hidden_labels.json").write_text(json.dumps(labels, indent=1))
        print(json.dumps({"sessions": len(pairs), "should_fail": sum(c.curt for c, _ in pairs), "idle": sum(c.idle for c, _ in pairs)}))
    else:
        pairs = build_hidden(a.seed, a.n)
        write_jsonl(a.out / "hidden.jsonl", [r for _, r in pairs])
        labels = {c.external_id: {"affected": c.affected, "currency": c.currency, "method": c.method, "style": c.reply_style, "release": c.version} for c, _ in pairs}
        (a.out / "hidden_labels.json").write_text(json.dumps(labels, indent=1))
        print(json.dumps({"sessions": len(pairs), "affected": sum(c.affected for c, _ in pairs)}))


if __name__ == "__main__":
    main()
