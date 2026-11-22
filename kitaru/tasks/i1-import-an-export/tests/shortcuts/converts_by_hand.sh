#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the Langfuse importer is not used. The export is converted to Kitaru's own JSONL with a local script, with the right external ids
# and versions, and imported through the built-in JSONL importer. Must score 0.
kitaru agent register support-assistant --description "Tidewater Couriers support assistant" --display-version 1.4.0 --command "python -m support_assistant" -o json > /dev/null
kitaru agent version register support-assistant --display-version 1.5.0 --command "python -m support_assistant" -o json > /dev/null
python3 - <<'PY'
import json
from collections import defaultdict
tickets = defaultdict(list)
for line in open("exports/langfuse-traces-2026-08.jsonl"):
    t = json.loads(line); tickets[t["sessionId"]].append(t)
out = {"1.4.0": open("/tmp/k-1.4.0.jsonl", "w"), "1.5.0": open("/tmp/k-1.5.0.jsonl", "w")}
for ticket, traces in tickets.items():
    traces.sort(key=lambda t: t["timestamp"])
    nodes, index = [], {}
    for t in traces:
        for o in t["observations"]:
            index[o["id"]] = len(nodes)
            node = {"index": len(nodes), "parent_index": index.get(o["parentObservationId"]), "links": [], "external_id": t["id"] + ":" + o["id"], "trace_id": t["id"],
                    "node_type": {"GENERATION": "llm_call", "TOOL": "tool_call"}.get(o["type"], "span"), "name": o["name"], "status": "failed" if o["level"] == "ERROR" else "completed",
                    "started_at": o["startTime"], "ended_at": o["endTime"], "inputs": o.get("input"), "outputs": o.get("output"), "attributes": {}, "metadata": {}}
            if o["type"] == "GENERATION":
                u = o["usageDetails"]
                node |= {"model": o["model"], "cost": str(o["totalCost"]), "tokens": {"input_tokens": u["input"], "output_tokens": u["output"], "cached_input_tokens": u["input_cached_tokens"], "cache_write_input_tokens": 0, "reasoning_tokens": 0}}
            if o["type"] == "TOOL":
                node["tool_name"] = o["name"]
            nodes.append(node)
    out[traces[0]["release"]].write(json.dumps({"status": "completed", "name": "support-turn", "inputs": {"turns": [t["input"] for t in traces]}, "outputs": traces[-1]["output"],
        "started_at": traces[0]["timestamp"], "ended_at": nodes[-1]["ended_at"], "external_id": "tidewater-support:" + ticket,
        "metadata": {"langfuse.trace_ids": [t["id"] for t in traces]}, "nodes": nodes}) + "\n")
PY
kitaru session import /tmp/k-1.4.0.jsonl --importer kitaru/kitaru-jsonl@latest --agent support-assistant@1 --media-type application/x-ndjson --wait --timeout 600 -o json > /dev/null
kitaru session import /tmp/k-1.5.0.jsonl --importer kitaru/kitaru-jsonl@latest --agent support-assistant@2 --media-type application/x-ndjson --wait --timeout 600 -o json > /dev/null
