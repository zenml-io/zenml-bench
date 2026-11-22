#!/usr/bin/env bash
# Builds the state the task starts from: the team's importer registered as version 1, August's log imported through it.
# Runs as root while the image is built.
set -euo pipefail
kitaru importer register tw-trace --script /app/importers/tw_trace.py --entrypoint parse --provider tidewater --description "Dispatch assistant trace log (docs/trace-format.md)" -o json > /dev/null
kitaru session import /app/logs/2026-08.log.jsonl --importer tw-trace@1 --agent dispatch-agent@1 --media-type application/x-ndjson --wait --timeout 900 -o json > /dev/null
python3 - <<'PY'
import json, subprocess
def kitaru(*args):
    out = json.loads(subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True).stdout)
    assert out["ok"], out
    return out
sessions = kitaru("session", "list", "--agent", "dispatch-agent", "--size", "1000")["items"]
assert len(sessions) == 450, len(sessions)
json.dump({"importer_id": kitaru("importer", "get", "tw-trace")["item"]["id"], "version_id": kitaru("importer", "version", "get", "tw-trace@1")["item"]["id"],
           "agent_id": kitaru("agent", "get", "dispatch-agent")["item"]["id"]}, open("/etc/kitaru-bench/i5.json", "w"))
print("august imported:", len(sessions), "sessions, cost", sum(float(s["cost"] or 0) for s in sessions))
PY
chmod 600 /etc/kitaru-bench/i5.json   # the grader's record of what was registered before the agent started; root only
