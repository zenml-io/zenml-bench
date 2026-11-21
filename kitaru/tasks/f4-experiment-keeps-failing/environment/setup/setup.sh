#!/usr/bin/env bash
# Builds the state the task starts from: release 1.6.2 (euros fixed) registered as version 3, the team's `refund-amount`
# evaluator, a cohort of every recorded refund, and an experiment whose one run has failed. Runs as root while the image is built.
set -euo pipefail
kitaru evaluator register refund-amount --script /app/evaluators/refund_amount.py --entrypoint evaluate --description "Passes when every refund is the order's total." -o json > /dev/null
kitaru agent version register helpdesk-agent --display-version 1.6.2 --command "python -m helpdesk.agent" --working-dir /app/releases/1.6.2 --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
python3 - <<'PY'
import asyncio, json, subprocess, sys, tempfile, time
from kitaru.client import KitaruAPIClient
def cli(*args):
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        return json.loads(out.stdout or out.stderr)
    except ValueError:
        return {"ok": False, "raw": (out.stdout + out.stderr)[-400:]}
async def _recorded():
    """Every recorded conversation with its nodes, as {"id", "name", "refund": the issue_refund arguments or None}."""
    async with KitaruAPIClient() as client:
        ids = [s.id async for s in client.sessions.iter() if str(s.origin).endswith("recorded")]
        gate = asyncio.Semaphore(8)
        async def one(i):
            async with gate:
                d = (await client.sessions.get_with_nodes(i)).model_dump(mode="json")
                calls = [n["inputs"] for n in d["nodes"] if n["node_type"] == "tool_call" and n.get("tool_name") == "issue_refund"]
                return {"id": d["session"]["id"], "name": d["session"]["name"], "refund": calls[0] if calls else None}
        return await asyncio.gather(*(one(i) for i in ids))
RECORDED = sorted(asyncio.run(_recorded()), key=lambda s: s["name"] or "")
REFUNDS = [s for s in RECORDED if s["refund"]]
EUROS = [s for s in REFUNDS if s["refund"]["currency"] == "EUR"]
HISTORY = {"type": "history", "scope": "baseline", "on_miss": "fail"}
STATIC = lambda result: {"type": "static", "on_miss": "fail", "cases": [{"match_mode": "subset", "match": {}, "result": result}]}
SAFE = {"default": HISTORY, "tools": {"issue_refund": STATIC({"receipt": "rf_not_sent", "status": "issued"}), "escalate_to_human": STATIC({"case": "cs_not_sent", "status": "paged"})}}
def cohort(name, sessions):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("".join(s["id"] + "\n" for s in sessions))
    print("cohort", name, len(sessions), cli("cohort", "create", name, "--agent", "helpdesk-agent", "--sessions-file", f.name).get("ok"))
    return cli("cohort", "version", "get", f"{name}@1")["item"]["id"]
def experiment(name, cohort_version, agent, policy=SAFE, evaluator="refund-amount@1"):
    extra = ["--tool-policy", json.dumps(policy)] if policy else []
    print("experiment", name, cli("experiment", "create", name, "--agent", "helpdesk-agent", "--evaluator", evaluator, *extra).get("ok"))
    run = cli("experiment", "run", "start", name, "--cohort-version", cohort_version, "--agent", agent, "--wait", "--timeout", "900")
    print("run", json.dumps((run.get("item") or {}).get("run", run))[:300])


import os
version = cohort("recorded-refunds", REFUNDS)
experiment("euro-fix", version, "helpdesk-agent@3", policy={"default": HISTORY})
runs = {r["experiment_run_id"] for r in cli("replay", "list", "--size", "1000")["items"] if r.get("experiment_run_id")}
assert len(runs) == 1, runs
run = cli("experiment", "run", "get", runs.pop())["item"]
run = run.get("run", run)
assert run["status"] == "failed", run
before = json.load(open("/etc/kitaru-bench/helpdesk.json"))
before |= {"f4": {"cohort_version_id": version, "cohort_size": len(REFUNDS), "version_3_id": run["agent_version_id"], "failed_run_id": run["id"]}}
json.dump(before, open("/etc/kitaru-bench/helpdesk.json", "w"))
os.chmod("/etc/kitaru-bench/helpdesk.json", 0o600)
print("f4 state ready:", len(REFUNDS), "refunds in the cohort; the first run", run["status"], run["progress"])
PY
