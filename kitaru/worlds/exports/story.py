# /// script
# requires-python = ">=3.11"
# ///
"""The exports world: a courier company whose dispatch assistant writes its own trace log.

Tidewater Couriers never used a tracing product. Its dispatch assistant appends one JSON line per
event to a log file, in a format the team made up (`workspace/docs/trace-format.md` describes it).
Kitaru has no importer for it. This world holds no recorded history: the tasks on it are about getting
that log into Kitaru.

    python story.py sample --out <dir>                 # sample.log.jsonl: the log the agent can read
    python story.py hidden --seed 7 --n 150 --out <dir>   # hidden.log.jsonl + hidden_expected.json for a grader
    python story.py history --out <dir>                # what sync_env.sh calls: an empty plan and the sample's expected sessions

One seeded plan produces every conversation as plain data; `events` renders it as log lines and
`expected` as what Kitaru should hold after a correct import. No model is called.

What the log does that an importer has to cope with (every one of these is in the sample too):

- conversations overlap, so their lines are interleaved in the file
- a tool call can be made by another tool call (`parent` names a tool span)
- some model calls report cached input tokens, some have no `cached` key at all
- some tool calls fail (`ok: false`)
- some conversations end with `outcome: error`, and some never get an `end` line
- now and then a line is cut off mid-write and is not valid JSON
"""
import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

START = datetime(2026, 8, 3, 6, 0, tzinfo=timezone.utc)
MODEL = "gpt-5.4-mini"
DEPOTS = ["Harbour Road", "Mill Lane", "Northgate", "Quayside"]
ASKS = ["Where is parcel {p}?", "Can you redeliver {p} tomorrow?", "Parcel {p} arrived damaged, what now?", "Change the address for {p} please.", "Why is {p} late?"]
SAMPLE_SEED, SAMPLE_N = 20260803, 60


def iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def plan(seed: int, n: int, prefix: str) -> list[dict[str, Any]]:
    """`n` conversations as structured data: each has spans (model calls and tool calls) with a parent."""
    rng = random.Random(seed)
    out = []
    clock = START
    for number in range(1, n + 1):
        clock += timedelta(seconds=rng.uniform(0.5, 7))  # starts are close together, so conversations overlap
        t = clock
        conv = f"{prefix}-{number:05d}"
        parcel = f"TW{rng.randrange(10**7, 10**8)}"
        message = rng.choice(ASKS).format(p=parcel)
        spans: list[dict[str, Any]] = []

        def span(kind: str, seconds: float, parent: str | None, **fields: Any) -> str:
            nonlocal t
            begin, t = t, t + timedelta(seconds=seconds)
            spans.append({"span": f"s{len(spans) + 1}", "kind": kind, "parent": parent, "start": begin, "end": t, **fields})
            return spans[-1]["span"]

        def llm(parent: str | None = None) -> str:
            tokens_in, tokens_out = rng.randrange(300, 1400), rng.randrange(20, 160)
            cached = rng.choice([None, None, 0, tokens_in // 2 // 64 * 64])  # None = the key is absent from the line
            micro = round(tokens_in * 0.25 + tokens_out * 2.0 - (cached or 0) * 0.2)
            return span("llm", rng.uniform(0.5, 2.0), parent, model=MODEL, tokens_in=tokens_in, tokens_out=tokens_out, cached=cached, cost_microusd=micro)

        def tool(name: str, parent: str | None, ok: bool = True) -> str:
            return span("tool", rng.uniform(0.05, 0.6), parent, tool=name, ok=ok, args={"parcel": parcel}, result={"depot": rng.choice(DEPOTS)} if ok else {"error": "upstream timeout"})

        first = llm()
        tool("find_parcel", first, ok=rng.random() > 0.08)
        if rng.random() < 0.45:  # a route plan, whose tool calls the geocoder itself: a tool under a tool
            second = llm()
            route = tool("plan_route", second)
            for _ in range(rng.choice([1, 1, 2])):
                tool("geocode", route, ok=rng.random() > 0.1)
        if rng.random() < 0.3:
            tool("notify_customer", llm())
        llm()
        roll = rng.random()
        outcome = "resolved" if roll < 0.84 else "error" if roll < 0.93 else None  # None = the log has no end line
        out.append({"conv": conv, "start": clock, "message": message, "channel": rng.choice(["sms", "app", "web"]), "spans": spans, "outcome": outcome,
                    "end": t + timedelta(seconds=0.2) if outcome else None, "reply": f"Parcel {parcel}: handled." if outcome == "resolved" else None,
                    "error": "dispatch assistant crashed: KeyError 'depot'" if outcome == "error" else None})
    return out


def events(conversations: list[dict[str, Any]], seed: int, broken_lines: int) -> list[str]:
    """The log file: every event of every conversation as one line, in time order, epoch seconds.
    `broken_lines` extra lines are cut off part-way, as when the writer died mid-line."""
    rows: list[tuple[datetime, dict[str, Any]]] = []
    for c in conversations:
        rows.append((c["start"], {"conv": c["conv"], "kind": "start", "ts": c["start"].timestamp(), "customer_msg": c["message"], "channel": c["channel"]}))
        for s in c["spans"]:
            line = {"conv": c["conv"], "kind": s["kind"], "span": s["span"], "parent": s["parent"], "ts_start": s["start"].timestamp(), "ts_end": s["end"].timestamp()}
            if s["kind"] == "llm":
                usage = {"in": s["tokens_in"], "out": s["tokens_out"]} | ({} if s["cached"] is None else {"cached": s["cached"]})
                line |= {"model": s["model"], "usage": usage, "cost_microusd": s["cost_microusd"]}
            else:
                line |= {"tool": s["tool"], "ok": s["ok"], "args": s["args"], "result": s["result"]}
            rows.append((s["end"], line))  # a span is written when it finishes
        if c["outcome"]:
            rows.append((c["end"], {"conv": c["conv"], "kind": "end", "ts": c["end"].timestamp(), "outcome": c["outcome"]} | ({"reply": c["reply"]} if c["reply"] else {"error": c["error"]})))
    rows.sort(key=lambda r: r[0])
    lines = [json.dumps(r, separators=(",", ":")) for _, r in rows]
    rng = random.Random(f"{seed}/broken")
    for _ in range(broken_lines):
        at = rng.randrange(5, len(lines))
        lines.insert(at, lines[at - 1][: rng.randrange(15, 40)])  # the first part of a real line, cut off
    return lines


def expected(conversations: list[dict[str, Any]]) -> dict[str, Any]:
    """What Kitaru should hold for each conversation after a correct import, keyed by conversation id."""
    out = {}
    for c in conversations:
        spans = {s["span"]: s for s in c["spans"]}
        nodes = []
        for s in c["spans"]:
            parent = spans.get(s["parent"]) if s["parent"] else None
            node: dict[str, Any] = {"type": "llm_call" if s["kind"] == "llm" else "tool_call", "started_at": iso(s["start"]), "ended_at": iso(s["end"]),
                    "parent_started_at": iso(parent["start"]) if parent else None}
            if s["kind"] == "llm":
                node |= {"model": s["model"], "input_tokens": s["tokens_in"], "output_tokens": s["tokens_out"], "cached_input_tokens": s["cached"] or 0, "cost": s["cost_microusd"] / 1_000_000}
            else:
                node |= {"tool_name": s["tool"], "status": "completed" if s["ok"] else "failed"}
            nodes.append(node)
        out[c["conv"]] = {"status": "completed" if c["outcome"] == "resolved" else "failed", "started_at": iso(c["start"]),
                          "ended_at": iso(c["end"] or c["spans"][-1]["end"]), "reply": c["reply"], "message": c["message"],
                          "cost": round(sum(s.get("cost_microusd", 0) for s in c["spans"]) / 1_000_000, 6), "nodes": nodes}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["sample", "hidden", "history"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--plants", default=None, help="unused; accepted so sync_env.sh can call every world the same way")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sample = plan(SAMPLE_SEED, SAMPLE_N, "tw")
    if a.mode == "sample":
        (a.out / "sample.log.jsonl").write_text("\n".join(events(sample, SAMPLE_SEED, 2)) + "\n")
        print(json.dumps({"conversations": len(sample), "no_end": sum(c["outcome"] is None for c in sample), "errors": sum(c["outcome"] == "error" for c in sample)}))
    elif a.mode == "hidden":
        hidden = plan(a.seed, a.n, "tx")
        (a.out / "hidden.log.jsonl").write_text("\n".join(events(hidden, a.seed, 3)) + "\n")
        (a.out / "hidden_expected.json").write_text(json.dumps({"broken_lines": 3, "sessions": expected(hidden)}, indent=1))
        print(json.dumps({"conversations": len(hidden), "no_end": sum(c["outcome"] is None for c in hidden), "nested_tools": sum(s["kind"] == "tool" and s["tool"] == "geocode" for c in hidden for s in c["spans"])}))
    else:  # no recorded history in this world; the answer key for the visible sample goes to the grader's fixtures
        (a.out / "ground_truth.json").write_text(json.dumps({"sessions": 0, "by_version": {}, "sample": expected(sample)}, indent=1))


if __name__ == "__main__":
    main()
