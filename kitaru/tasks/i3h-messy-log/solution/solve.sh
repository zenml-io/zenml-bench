#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Reference: as I3's importer, plus: both timestamp forms, one node for a line written twice, and a batch call's cost from the price list.
mkdir -p importers
cat > importers/tw_trace.py <<'PYEOF'
"""Importer for the dispatch assistant's trace log (docs/trace-format.md)."""
import json
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from kitaru.task.importer import ImportFailure, ImportedNode, ImportedSession


def when(value: float | str) -> datetime:
    """A time from the log: seconds since 1970 from the first writer, an ISO 8601 string with an offset from the second."""
    if isinstance(value, str):
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    return datetime.fromtimestamp(value, tz=timezone.utc)


PRICES = {"gpt-5.4-mini": ("0.25", "0.05", "2.0"), "gpt-5.4": ("0.3", "0.06", "1.6")}  # US dollars per million tokens: input, cached input, output


def cost(e: dict[str, Any]) -> Decimal:
    """The call's cost in dollars: from the line, or for a batch call from its tokens and the price list."""
    if "cost_microusd" in e:
        return Decimal(e["cost_microusd"]) / Decimal(1_000_000)
    usage = e.get("usage") or {}
    cached = usage.get("cached", 0)
    price_in, price_cached, price_out = (Decimal(p) for p in PRICES[e["model"]])
    return ((usage.get("in", 0) - cached) * price_in + cached * price_cached + usage.get("out", 0) * price_out) / Decimal(1_000_000)


def parse(payload: bytes, params: dict[str, Any]) -> Iterator[ImportedSession | ImportFailure]:
    conversations: dict[str, list[dict[str, Any]]] = {}
    for number, line in enumerate(payload.decode("utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            conversations.setdefault(event["conv"], []).append(event)
        except (ValueError, KeyError, TypeError) as error:
            yield ImportFailure(line=number, error=f"not a trace event: {error}")
    for conv, events in conversations.items():
        start = next((e for e in events if e["kind"] == "start"), None)
        end = next((e for e in events if e["kind"] == "end"), None)
        spans = list({e["span"]: e for e in events if e["kind"] in ("llm", "tool")}.values())  # a line written twice is one call
        if start is None:
            yield ImportFailure(line=0, external_id=conv, error="conversation has no start event")
            continue
        nodes = []
        for e in sorted(spans, key=lambda e: when(e["ts_start"])):
            common = dict(external_id=f"{conv}:{e['span']}", parent_external_id=f"{conv}:{e['parent']}" if e.get("parent") else None, trace_id=conv,
                          started_at=when(e["ts_start"]), ended_at=when(e["ts_end"]), attributes={}, metadata={})
            if e["kind"] == "llm":
                usage = e.get("usage") or {}
                nodes.append(ImportedNode(node_type="llm_call", name="dispatch assistant turn", status="completed", inputs=None, outputs=None,
                                          requested_model=e.get("model"), model=e.get("model"),
                                          tokens={"input_tokens": usage.get("in", 0), "output_tokens": usage.get("out", 0), "cached_input_tokens": usage.get("cached", 0),
                                                  "cache_write_input_tokens": 0, "reasoning_tokens": 0},
                                          cost=cost(e), **common))
            else:
                failed = not e.get("ok", True)
                nodes.append(ImportedNode(node_type="tool_call", name=e["tool"], tool_name=e["tool"], status="failed" if failed else "completed",
                                          error=json.dumps(e.get("result")) if failed else None, inputs=e.get("args"), outputs=e.get("result"), **common))
        resolved = end is not None and end.get("outcome") == "resolved"
        last = when(end["ts"]) if end else max([when(e["ts_end"]) for e in spans] or [when(start["ts"])])
        yield ImportedSession(status="completed" if resolved else "failed", name=f"Dispatch: {conv}", inputs={"message": start.get("customer_msg")},
                              outputs={"reply": end.get("reply")} if resolved else None, error=None if resolved else (end or {}).get("error") or "the log has no end line for this conversation",
                              started_at=when(start["ts"]), ended_at=last, external_id=conv, metadata={"channel": start.get("channel")}, nodes=nodes)
PYEOF
kitaru importer register tw-trace --script importers/tw_trace.py --entrypoint parse --provider tidewater -o json > /dev/null
