# /// script
# requires-python = ">=3.11"
# ///
"""The exports world's second assistant: Tidewater Couriers' support assistant, which was traced with Langfuse.

The support team is moving from Langfuse to Kitaru. This file writes the Langfuse export files the import
tasks hand to an agent, and what Kitaru should hold after each is imported correctly. No model is called
and no Langfuse is involved: the files only have the shape of Langfuse's exports.

    python support.py releases --out <dir>                    # I1: one export, two releases of the assistant
    python support.py tickets --seed 11 --n 70 --prefix TK-1 --out <dir>   # I2: one trace per turn, the ticket id in metadata
    python support.py nightly --out <dir>                     # I4: one file per night, each covering the last two days

A ticket is one customer conversation of one to four turns. Langfuse recorded each turn as one trace: a
root span, the model calls and the tool calls under it.
"""
import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT = "tidewater-support"
START = datetime(2026, 8, 1, 7, 0, tzinfo=timezone.utc)
MODEL = "gpt-5.4-mini"
ASKS = ["Where is my parcel {p}?", "Parcel {p} arrived damaged.", "I was not home, can you redeliver {p}?", "I was charged twice for {p}.", "Please change the delivery address for {p}."]
FOLLOW_UPS = ["Thanks. And when will it arrive?", "That does not help, can a person call me?", "OK, please go ahead.", "Can you send that by email as well?"]
TOOLS = ["lookup_shipment", "open_claim", "schedule_redelivery", "send_email"]


def iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def tickets(seed: int, n: int, prefix: str, days: int = 1, releases: tuple[str, ...] = ("1.4.0",)) -> list[dict[str, Any]]:
    """`n` tickets as plain data, spread evenly over `days` days. Each has turns; each turn has observations."""
    rng = random.Random(seed)
    out = []
    for number in range(1, n + 1):
        day = (number - 1) * days // n
        t = START + timedelta(days=day, seconds=rng.uniform(0, 11 * 3600))
        ticket = f"{prefix}{number:04d}"
        parcel = f"TW{rng.randrange(10**7, 10**8)}"
        customer = f"cust-{rng.randrange(1000, 9999)}"
        release = releases[min(len(releases) - 1, (number - 1) * len(releases) // n)] if rng.random() > 0.12 else rng.choice(releases)
        turns = []
        for turn_number in range(rng.choice([1, 1, 2, 2, 3, 4])):
            trace = f"{rng.getrandbits(128):032x}"
            observations: list[dict[str, Any]] = []
            clock = t

            def add(kind: str, name: str, seconds: float, parent: str | None, **fields: Any) -> str:
                nonlocal clock
                begin, clock = clock, clock + timedelta(seconds=seconds)
                observations.append({"id": f"{rng.getrandbits(64):016x}", "kind": kind, "name": name, "parent": parent, "start": begin, "end": clock, **fields})
                return observations[-1]["id"]

            def generation(parent: str) -> None:
                tokens_in, tokens_out = rng.randrange(400, 1800), rng.randrange(30, 220)
                cached = rng.choice([0, 0, tokens_in // 2 // 64 * 64])
                add("GENERATION", "chat " + MODEL, rng.uniform(0.6, 2.4), parent, tokens_in=tokens_in, tokens_out=tokens_out, cached=cached,
                    cost=round(tokens_in * 0.25 + tokens_out * 2.0 - cached * 0.2) / 1_000_000)

            message = ASKS[rng.randrange(len(ASKS))].format(p=parcel) if turn_number == 0 else rng.choice(FOLLOW_UPS)
            reply = f"Ticket {ticket}, turn {turn_number + 1}: {rng.choice(['done', 'noted', 'on its way', 'a colleague will call'])}."
            root = add("SPAN", "support-turn", 0.01, None)
            generation(root)
            for _ in range(rng.choice([0, 1, 1, 2])):
                add("TOOL", rng.choice(TOOLS), rng.uniform(0.05, 0.7), root, ok=rng.random() > 0.07)
                generation(root)
            observations[0]["end"] = clock  # the root span covers the whole turn
            turns.append({"trace": trace, "start": t, "message": message, "reply": reply, "observations": observations})
            t = clock + timedelta(seconds=rng.uniform(20, 400))
        out.append({"ticket": ticket, "customer": customer, "day": day, "release": release, "channel": rng.choice(["web", "app"]), "turns": turns})
    return out


def observation_row(ticket: dict[str, Any], turn: dict[str, Any], o: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"id": o["id"], "traceId": turn["trace"], "type": o["kind"], "name": o["name"], "startTime": iso(o["start"]), "endTime": iso(o["end"]),
                           "parentObservationId": o["parent"], "level": "DEFAULT"}
    if o["kind"] == "SPAN":
        row |= {"input": {"message": turn["message"]}, "output": {"reply": turn["reply"]}}
    elif o["kind"] == "GENERATION":
        row |= {"model": MODEL, "usageDetails": {"input": o["tokens_in"], "output": o["tokens_out"], "input_cached_tokens": o["cached"]}, "totalCost": o["cost"]}
    else:
        row |= {"input": {"ticket": ticket["ticket"]}, "output": {"ok": True} if o["ok"] else None}
        if not o["ok"]:
            row |= {"level": "ERROR", "statusMessage": "upstream timeout"}
    return row | extra


def trace_rows(found: list[dict[str, Any]], session_id: bool = True) -> list[dict[str, Any]]:
    """Langfuse's trace export: one object per trace, its observations inside it."""
    rows = []
    for ticket in found:
        for turn in ticket["turns"]:
            rows.append({"id": turn["trace"], "name": "support-turn", "timestamp": iso(turn["start"]), "release": ticket["release"], "userId": ticket["customer"],
                         "input": {"message": turn["message"]}, "output": {"reply": turn["reply"]}, "tags": [ticket["channel"]]} | ({"sessionId": ticket["ticket"]} if session_id else {})
                        | {"observations": [observation_row(ticket, turn, o, {}) for o in turn["observations"]]})
    rows.sort(key=lambda r: r["timestamp"])
    return rows


def expected(found: list[dict[str, Any]]) -> dict[str, Any]:
    """What Kitaru should hold per ticket: its turns in order, how many nodes of each kind, the cost."""
    out = {}
    for ticket in found:
        observations = [o for turn in ticket["turns"] for o in turn["observations"]]
        out[ticket["ticket"]] = {"release": ticket["release"], "day": ticket["day"], "traces": [turn["trace"] for turn in ticket["turns"]],
                                 "llm_calls": sum(o["kind"] == "GENERATION" for o in observations), "tool_calls": sum(o["kind"] == "TOOL" for o in observations),
                                 "failed_tool_calls": sum(o["kind"] == "TOOL" and not o["ok"] for o in observations),
                                 "cost": round(sum(o.get("cost", 0) for o in observations), 6), "started_at": iso(ticket["turns"][0]["start"])}
    return out


def ticket_export(seed: int, n: int, prefix: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """I2's export: observation rows. The chat widget's own session id is in `sessionId`, and it is not the
    ticket: one widget visit can hold two tickets, and a ticket can continue in a later visit. The ticket id is
    in each observation's metadata. A few monitoring probes have no ticket at all."""
    rng = random.Random(f"{seed}/widget")
    found = tickets(seed, n, prefix)
    rows = []
    visit = None
    for ticket in found:
        if visit is None or rng.random() > 0.3:  # 30 % of tickets share the widget visit of the ticket before
            visit = f"ws-{rng.getrandbits(40):010x}"
        for turn_number, turn in enumerate(ticket["turns"]):
            if turn_number and rng.random() < 0.3:  # the customer came back later: a new widget visit, same ticket
                visit = f"ws-{rng.getrandbits(40):010x}"
            extra = {"projectId": PROJECT, "sessionId": visit, "metadata": {"ticket": {"id": ticket["ticket"]}, "channel": ticket["channel"]}}
            rows += [observation_row(ticket, turn, o, extra) for o in turn["observations"]]
    for _ in range(max(3, n // 12)):  # probes: a trace of one span and one model call, with no ticket
        at = START + timedelta(seconds=rng.uniform(0, 11 * 3600))
        trace, root = f"{rng.getrandbits(128):032x}", f"{rng.getrandbits(64):016x}"
        common = {"traceId": trace, "level": "DEFAULT", "projectId": PROJECT, "sessionId": None, "metadata": {"probe": True}}
        rows.append({"id": root, "type": "SPAN", "name": "synthetic-probe", "startTime": iso(at), "endTime": iso(at + timedelta(seconds=1)), "parentObservationId": None,
                     "input": {"message": "ping"}, "output": {"reply": "pong"}} | common)
        rows.append({"id": f"{rng.getrandbits(64):016x}", "type": "GENERATION", "name": "chat " + MODEL, "startTime": iso(at), "endTime": iso(at + timedelta(seconds=1)),
                     "parentObservationId": root, "model": MODEL, "usageDetails": {"input": 12, "output": 2, "input_cached_tokens": 0}, "totalCost": 0.000007} | common)
    rows.sort(key=lambda r: (r["startTime"], r["traceId"], r["id"]))
    return rows, expected(found)


def write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))


NIGHTS, PER_DAY = 8, 24  # I4: files for nights 1..7 are in the workspace, night 8 is the grader's


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["releases", "tickets", "nightly"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--n", type=int, default=70)
    ap.add_argument("--prefix", default="TK-1")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == "releases":
        found = tickets(20260801, 90, "TK-3", releases=("1.4.0", "1.5.0"))
        write(a.out / "langfuse-traces-2026-08.jsonl", trace_rows(found))
        (a.out / "expected.json").write_text(json.dumps({"project": PROJECT, "tickets": expected(found)}, indent=1))
        print(json.dumps({"tickets": len(found), "by_release": {r: sum(t["release"] == r for t in found) for r in ("1.4.0", "1.5.0")}}))
    elif a.mode == "tickets":
        rows, want = ticket_export(a.seed, a.n, a.prefix)
        write(a.out / "export.jsonl", rows)
        (a.out / "expected.json").write_text(json.dumps({"project": PROJECT, "tickets": want}, indent=1))
        print(json.dumps({"tickets": len(want), "traces": len({r["traceId"] for r in rows}), "widget_sessions": len({r["sessionId"] for r in rows if r["sessionId"]})}))
    else:
        found = tickets(20260808, PER_DAY * NIGHTS, "TK-5", days=NIGHTS)
        for night in range(1, NIGHTS + 1):  # the file written after day `night` holds that day and the day before
            write(a.out / f"support-2026-08-{night:02d}.jsonl", trace_rows([t for t in found if t["day"] + 1 in (night - 1, night)]))
        (a.out / "expected.json").write_text(json.dumps({"project": PROJECT, "tickets": expected(found)}, indent=1))
        print(json.dumps({"tickets": len(found), "per_day": PER_DAY}))


if __name__ == "__main__":
    main()
