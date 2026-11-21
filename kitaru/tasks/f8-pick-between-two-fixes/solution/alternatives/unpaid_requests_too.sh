#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: the cohort also holds the requests for one item that were refused, and misses of any lookup ask the live service.
python3 - <<'PY'
import asyncio, json, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from kitaru.client import KitaruAPIClient
def cli(*args):
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        return json.loads(out.stdout or out.stderr)
    except ValueError:
        return {"ok": False, "raw": (out.stdout + out.stderr)[-400:]}
def every(*args):
    """Every item of a list command, following the page cursor."""
    items, cursor = [], None
    while True:
        page = cli(*args, "--size", "1000", *(["--cursor", cursor] if cursor else []))
        items += page["items"]
        cursor = (page.get("page") or {}).get("next_cursor")
        if not cursor:
            return items
async def _sessions(ids=None):
    """Conversations with their tool calls in order: {"id", "name", "prompt", "calls": [{"tool", "inputs", "outputs"}], "answer"}. Every recorded one unless `ids` is given."""
    async with KitaruAPIClient() as client:
        ids = ids or [s.id async for s in client.sessions.iter() if str(s.origin).endswith("recorded")]
        gate = asyncio.Semaphore(8)
        async def one(i):
            async with gate:
                d = (await client.sessions.get_with_nodes(i)).model_dump(mode="json")
                nodes = sorted(d["nodes"], key=lambda n: n.get("started_at") or "")
                texts = [p.get("content") for n in nodes if n["node_type"] == "llm_call" for p in ((n.get("outputs") or {}).get("parts") or []) if p.get("part_kind") == "text"]
                return {"id": d["session"]["id"], "name": d["session"]["name"], "prompt": str(d["session"].get("inputs") or ""), "answer": re.sub(r"(rf|cs)_\w+", "#", texts[-1]) if texts else None,
                        "calls": [{"tool": n.get("tool_name"), "inputs": n.get("inputs"), "outputs": n.get("outputs")} for n in nodes if n["node_type"] == "tool_call"]}
        return await asyncio.gather(*(one(i) for i in ids))
RECORDED = sorted(asyncio.run(_sessions()), key=lambda s: s["name"] or "")
HISTORY = {"type": "history", "scope": "baseline", "on_miss": "fail"}
STATIC = lambda result: {"type": "static", "on_miss": "fail", "cases": [{"match_mode": "subset", "match": {}, "result": result}]}
SAFE = {"default": HISTORY, "tools": {"issue_refund": STATIC({"receipt": "rf_not_sent", "status": "issued"}), "escalate_to_human": STATIC({"case": "cs_not_sent", "status": "paged"})}}
def cohort(name, sessions):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("".join(s["id"] + "\n" for s in sessions))
    print("cohort", name, len(sessions), cli("cohort", "create", name, "--agent", "helpdesk-agent", "--sessions-file", f.name).get("ok"))
    return cli("cohort", "version", "get", f"{name}@1")["item"]["id"]
def experiment(name, cohort_version, agent, policy=SAFE, evaluator="refund-once@1", override=None):
    """Create an experiment, run it once over a cohort version and wait. Returns the run's replays."""
    extra = (["--tool-policy", json.dumps(policy)] if policy else []) + (["--override", json.dumps(override)] if override else [])
    made = cli("experiment", "create", name, "--agent", "helpdesk-agent", "--evaluator", evaluator, *extra)
    print("experiment", name, made.get("ok") or json.dumps(made)[:300])
    before = {r["experiment_run_id"] for r in every("replay", "list")}
    run = cli("experiment", "run", "start", name, "--cohort-version", cohort_version, "--agent", agent, "--wait", "--timeout", "1200")
    replays = [r for r in every("replay", "list") if r.get("experiment_run_id") and r["experiment_run_id"] not in before]
    print("run:", len(replays), "replays,", {st: sum(r["status"] == st for r in replays) for st in sorted({r["status"] for r in replays})}, "" if run.get("ok") else "(the run settled as failed)")
    return replays

partial = [s for s in RECORDED if "refund only the" in s["prompt"] and any(c["tool"] == "issue_refund" for c in s["calls"])]
WITH_LINES = SAFE | {"tools": SAFE["tools"] | {"get_line_total": {"type": "passthrough"}}}
asked = [s for s in RECORDED if "refund only the" in s["prompt"]]
version = cohort("asked-for-one-item", asked)
LIVE_MISSES = {"default": {"type": "history", "scope": "baseline", "on_miss": "passthrough"}, "tools": SAFE["tools"]}
experiment("one-item-ana", version, "helpdesk-agent@2", evaluator="refund-amount@1", policy=LIVE_MISSES)
experiment("one-item-ben", version, "helpdesk-agent@3", evaluator="refund-amount@1", policy=LIVE_MISSES)
PY
cp -R releases/2.0.1-ben releases/2.0.1
find releases/2.0.1 -name __pycache__ -prune -exec rm -rf {} +
sed -i 's/__version__ = "2.0.1-ben"/__version__ = "2.0.1"/' releases/2.0.1/helpdesk/__init__.py
kitaru agent version register helpdesk-agent --display-version 2.0.1 --command "python -m helpdesk.agent" --working-dir /app/releases/2.0.1 --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human --tool get_line_total -o json > /dev/null
