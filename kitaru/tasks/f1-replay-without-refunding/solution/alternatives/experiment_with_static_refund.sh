#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: one experiment over the cohort. Lookups run live (they only read); `issue_refund` and `escalate_to_human` get a fixed answer and are never called.
python3 - <<'PY'
import json, subprocess, sys, time
def cli(*args):
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        return json.loads(out.stdout or out.stderr)
    except ValueError:
        return {"ok": False, "raw": (out.stdout + out.stderr)[-400:]}
def members(cohort="refunds-to-recheck@1"):
    return [s["id"] for s in cli("session", "list", "--cohort", cohort, "--size", "1000")["items"]]
def replay_all(sessions, agent="helpdesk-agent@2", policy=None):
    """Create one replay per session and wait until every one has settled."""
    extra = ["--tool-policy", json.dumps(policy)] if policy else []
    ids = [cli("replay", "create", s, "--evaluator", "refund-once@1", "--agent", agent, *extra)["item"]["id"] for s in sessions]
    deadline = time.time() + 900
    while time.time() < deadline:
        states = [cli("replay", "get", i)["item"]["status"] for i in ids]
        if all(s in ("completed", "failed", "cancelled") for s in states):
            break
        time.sleep(2)
    print(len(ids), "replays:", {s: states.count(s) for s in set(states)})
HISTORY = {"type": "history", "scope": "baseline", "on_miss": "fail"}
STATIC_REFUND = {"type": "static", "on_miss": "fail", "cases": [{"match_mode": "subset", "match": {}, "result": {"receipt": "rf_replay_not_sent", "status": "issued"}}]}

policy = {"default": {"type": "passthrough"}, "tools": {"issue_refund": STATIC_REFUND, "escalate_to_human": STATIC_REFUND}}
print(cli("experiment", "create", "recheck-1-6-1", "--agent", "helpdesk-agent", "--evaluator", "refund-once@1", "--tool-policy", json.dumps(policy)).get("ok"))
version = cli("cohort", "version", "get", "refunds-to-recheck@1")["item"]["id"]
run = cli("experiment", "run", "start", "recheck-1-6-1", "--cohort-version", version, "--agent", "helpdesk-agent@2", "--wait", "--timeout", "900")
print(json.dumps(run)[:400])
PY
