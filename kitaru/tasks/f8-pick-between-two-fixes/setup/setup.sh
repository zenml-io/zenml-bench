#!/usr/bin/env bash
# Builds the state the task starts from. Runs as root while the image is built.
set -euo pipefail
kitaru evaluator register refund-amount --script /app/evaluators/refund_amount.py --entrypoint evaluate --description "Passes when a refund is the amount the customer was owed." -o json > /dev/null
kitaru agent version register helpdesk-agent --display-version 2.0.1-ana --command "python -m helpdesk.agent" --working-dir /app/releases/2.0.1-ana --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
kitaru agent version register helpdesk-agent --display-version 2.0.1-ben --command "python -m helpdesk.agent" --working-dir /app/releases/2.0.1-ben --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human --tool get_line_total -o json > /dev/null
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

import os
partial = [s for s in RECORDED if "refund only the" in s["prompt"] and any(c["tool"] == "issue_refund" for c in s["calls"])]
def line(s):
    order = [c["outputs"] for c in s["calls"] if c["tool"] == "lookup_order" and "items" in c["outputs"]][-1]
    return next(i for i in order["items"] if i["name"] == re.search(r"refund only the ([a-z ]+)\.", s["prompt"]).group(1))
simple = [s for s in partial if line(s)["quantity"] == 1 and line(s)["discount_minor"] == 0][:24]
print(len(partial), "recorded refunds of one item;", len(simple), "of them with one unit and no discount")
ana = experiment("ana-item-refund", cohort("partial-refunds-ana", simple), "helpdesk-agent@2", evaluator="refund-amount@1")
ben = experiment("ben-line-total", cohort("partial-refunds-ben", partial), "helpdesk-agent@3", evaluator="refund-amount@1")
assert len(ana) == len(simple) and all(r["status"] == "completed" for r in ana), "Ana's run should complete"
assert len(ben) == len(partial) and all(r["status"] == "failed" for r in ben), "Ben's run should fail on the tool the recordings do not have"
verdicts = {e["session_id"]: e["passed"] for e in every("evaluation", "list") if e.get("evaluator_name") == "refund-amount"}
print("Ana's run: results passing", sum(verdicts.get(r["result_session_id"]) is True for r in ana), "of", len(ana), "; recordings passing", sum(verdicts.get(r["baseline_session_id"]) is True for r in ana))
before = json.load(open("/etc/kitaru-bench/helpdesk.json"))
versions = {v["display_version"]: v["id"] for v in every("agent", "version", "list", "helpdesk-agent")}
before["versions"] |= versions
json.dump(before, open("/etc/kitaru-bench/helpdesk.json", "w"))
os.chmod("/etc/kitaru-bench/helpdesk.json", 0o600)
print("versions", sorted(versions))
PY
