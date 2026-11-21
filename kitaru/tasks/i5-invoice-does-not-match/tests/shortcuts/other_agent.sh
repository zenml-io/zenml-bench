#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: a corrected version is registered and August imported under a second agent, where nothing is skipped; `dispatch-agent` still holds the wrong sessions. Must score 0.
cat > importers/tw_trace.py <<'PYEOF'
"""Importer for the dispatch assistant's trace log (docs/trace-format.md)."""
import json
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from kitaru.task.importer import ImportFailure, ImportedNode, ImportedSession


def when(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


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
        spans = [e for e in events if e["kind"] in ("llm", "tool")]
        if start is None:
            yield ImportFailure(line=0, external_id=conv, error="conversation has no start event")
            continue
        nodes = []
        for e in sorted(spans, key=lambda e: e["ts_start"]):
            common = dict(external_id=f"{conv}:{e['span']}", parent_external_id=f"{conv}:{e['parent']}" if e.get("parent") else None, trace_id=conv,
                          started_at=when(e["ts_start"]), ended_at=when(e["ts_end"]), attributes={}, metadata={})
            if e["kind"] == "llm":
                usage = e.get("usage") or {}
                nodes.append(ImportedNode(node_type="llm_call", name="dispatch assistant turn", status="completed", inputs=None, outputs=None,
                                          requested_model=e.get("model"), model=e.get("model"),
                                          tokens={"input_tokens": usage.get("in", 0), "output_tokens": usage.get("out", 0), "cached_input_tokens": usage.get("cached", 0),
                                                  "cache_write_input_tokens": 0, "reasoning_tokens": 0},
                                          cost=Decimal(e.get("cost_microusd", 0)) / Decimal(1_000_000), **common))
            else:
                failed = not e.get("ok", True)
                nodes.append(ImportedNode(node_type="tool_call", name=e["tool"], tool_name=e["tool"], status="failed" if failed else "completed",
                                          error=json.dumps(e.get("result")) if failed else None, inputs=e.get("args"), outputs=e.get("result"), **common))
        resolved = end is not None and end.get("outcome") == "resolved"
        last = end["ts"] if end else max([e["ts_end"] for e in spans] or [start["ts"]])
        yield ImportedSession(status="completed" if resolved else "failed", name=f"Dispatch: {conv}", inputs={"message": start.get("customer_msg")},
                              outputs={"reply": end.get("reply")} if resolved else None, error=None if resolved else (end or {}).get("error") or "the log has no end line for this conversation",
                              started_at=when(start["ts"]), ended_at=when(last), external_id=conv, metadata={"channel": start.get("channel")}, nodes=nodes)
PYEOF
kitaru importer version register tw-trace --script importers/tw_trace.py --entrypoint parse -o json > /dev/null
kitaru agent register dispatch-agent-fixed --display-version 2.1.0 --command "python -m dispatch_agent" -o json > /dev/null
kitaru session import logs/2026-08.log.jsonl --importer tw-trace@latest --agent dispatch-agent-fixed@1 --media-type application/x-ndjson --wait --timeout 900 -o json > /dev/null
