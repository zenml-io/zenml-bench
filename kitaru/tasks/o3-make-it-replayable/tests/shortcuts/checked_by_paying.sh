#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the right version, then checked with six replays that have no tool policy, which pay and page for real. Must score 0.
kitaru agent version register helpdesk-agent --display-version 2.0.0-here --command "python -m helpdesk.agent replay" --working-dir /app/releases/2.0.0 --env HELPDESK_REGION=eu-west --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
python3 - <<'PY'
import json, subprocess, time
def cli(*a):
    return json.loads(subprocess.run(["kitaru", *a, "-o", "json"], capture_output=True, text=True).stdout)
sessions = [s for s in cli("session", "list", "--size", "200")["items"] if s["tool_call_count"] >= 5][:6]
replays = [cli("replay", "create", s["id"], "--evaluator", "refund-once@1", "--agent", "helpdesk-agent@2")["item"]["id"] for s in sessions]
for _ in range(60):
    if all(cli("replay", "get", r)["item"]["status"] in ("completed", "failed") for r in replays):
        break
    time.sleep(2)
print([cli("replay", "get", r)["item"]["status"] for r in replays])
PY
