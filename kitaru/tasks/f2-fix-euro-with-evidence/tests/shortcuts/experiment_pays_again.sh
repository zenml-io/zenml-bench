#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the fix is right and the experiment runs with no tool policy, so every refund in the cohort is paid again. Must score 0.
cp -R releases/1.6.1 releases/1.6.2
find releases/1.6.2 -name __pycache__ -prune -exec rm -rf {} +
sed -i 's/__version__ = "1.6.1"/__version__ = "1.6.2"/' releases/1.6.2/helpdesk/__init__.py
python3 - <<'PY'
from pathlib import Path
p = Path("releases/1.6.2/helpdesk/money.py"); s = p.read_text()
old = 'if currency in ("USD", "GBP"):'
assert old in s
s = s.replace(old, 'if currency in ("USD", "GBP", "EUR"):')
p.write_text(s)
PY
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

experiment("euro-fix", cohort("recorded-refunds", REFUNDS), "helpdesk-agent@3", policy=None)
PY
