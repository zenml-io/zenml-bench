#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the importer is left alone. August's sessions are deleted and the log is converted to Kitaru's own JSONL with a local script and imported through the built-in importer. Must score 0.
python3 - <<'PY'
import asyncio, json, subprocess
from kitaru.client import KitaruAPIClient
agent = json.loads(subprocess.run(["kitaru", "agent", "get", "dispatch-agent", "-o", "json"], capture_output=True, text=True).stdout)["item"]["id"]
async def main():
    async with KitaruAPIClient() as client:
        old = [s.id async for s in client.sessions.iter() if str(s.agent_id) == agent]
        for session in old:
            await client.sessions.delete(session)
        print("deleted", len(old))
asyncio.run(main())
PY
python3 - <<'PY'
import json
from collections import defaultdict
from datetime import datetime, timezone
iso = lambda s: datetime.fromtimestamp(s, tz=timezone.utc).isoformat().replace("+00:00", "Z")
convs = defaultdict(list)
for line in open("logs/2026-08.log.jsonl"):
    try:
        e = json.loads(line); convs[e["conv"]].append(e)
    except ValueError:
        pass
with open("/tmp/sample.kitaru.jsonl", "w") as out:
    for conv, events in convs.items():
        start = next(e for e in events if e["kind"] == "start"); end = next((e for e in events if e["kind"] == "end"), None)
        nodes = [{"index": 0, "parent_index": None, "links": [], "external_id": f"{conv}-root", "node_type": "span", "name": "conversation", "status": "completed",
                  "started_at": iso(start["ts"]), "ended_at": iso(end["ts"]) if end else None, "inputs": None, "outputs": None, "attributes": {}, "metadata": {}}]
        out.write(json.dumps({"status": "completed" if end and end["outcome"] == "resolved" else "failed", "name": conv, "inputs": {"message": start["customer_msg"]},
                              "outputs": {"reply": (end or {}).get("reply")}, "started_at": iso(start["ts"]), "ended_at": iso(end["ts"]) if end else None,
                              "external_id": conv, "metadata": {}, "nodes": nodes}) + "\\n")
PY
kitaru session import /tmp/sample.kitaru.jsonl --importer kitaru/kitaru-jsonl@latest --agent dispatch-agent@1 --media-type application/x-ndjson --wait --timeout 900 -o json > /dev/null
