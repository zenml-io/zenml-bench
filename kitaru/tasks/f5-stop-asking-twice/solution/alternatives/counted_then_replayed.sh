#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: count, for every place that asks again, how often the second answer differed from the first over all recorded conversations; remove the places where it never did;
# then replay 80 recorded conversations against the new release, lookups answered from the recordings and the finance tools given a fixed answer, and check that every replay completes with the recorded answer.
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
async def _sessions(ids=None):
    """Conversations with their tool calls in order: {"id", "name", "calls": [{"tool", "inputs", "outputs"}], "answer"}. Every recorded one unless `ids` is given."""
    async with KitaruAPIClient() as client:
        ids = ids or [s.id async for s in client.sessions.iter() if str(s.origin).endswith("recorded")]
        gate = asyncio.Semaphore(8)
        async def one(i):
            async with gate:
                d = (await client.sessions.get_with_nodes(i)).model_dump(mode="json")
                nodes = sorted(d["nodes"], key=lambda n: n.get("started_at") or "")
                texts = [p.get("content") for n in nodes if n["node_type"] == "llm_call" for p in ((n.get("outputs") or {}).get("parts") or []) if p.get("part_kind") == "text"]
                return {"id": d["session"]["id"], "name": d["session"]["name"], "answer": re.sub(r"(rf|cs)_\w+", "#", texts[-1]) if texts else None,
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
    run = cli("experiment", "run", "start", name, "--cohort-version", cohort_version, "--agent", agent, "--wait", "--timeout", "1200")
    run = (run.get("item") or {}).get("run", run)
    print("run", json.dumps(run)[:300])
    return [r for r in cli("replay", "list", "--size", "1000")["items"] if r.get("experiment_run_id") == run.get("id")]

def kind(s):
    tools = {c["tool"] for c in s["calls"]}
    return "refund" if "check_return_policy" in tools else "dispute" if "escalate_to_human" in tools or "lookup_customer" in tools else "status"
places = {}  # (kind of request, tool, what the first answer was) -> [second asks, second asks that differed]
for s in RECORDED:
    last = {}
    for c in s["calls"]:
        key = (c["tool"], json.dumps(c["inputs"], sort_keys=True))
        if key in last:
            first = last[key]
            what = "error" if "error" in first else first.get("carrier_status", "answered") if c["tool"] == "get_shipping_status" else "answered"
            tally = places.setdefault((kind(s), c["tool"], what), [0, 0])
            tally[0] += 1; tally[1] += c["outputs"] != first
        last[key] = c["outputs"]
for place, (asked, differed) in sorted(places.items()):
    print(place, "asked again", asked, "times; different answer", differed, "times")
CUTS = {("status", "lookup_order", "answered"): ('''        if careful and len(order["items"]) > 1 and len([r for r in got("lookup_order", order_id=order_id) if "error" not in r]) < 2:
            return "lookup_order", {"order_id": order_id}
''', ""),
        ("dispute", "lookup_customer", "answered"): ('if len(got("lookup_customer", email=email)) < 2:', 'if not got("lookup_customer", email=email):'),
        ("refund", "check_return_policy", "answered"): ('''        if careful and len(checks) < 2:
            return "check_return_policy", {"order_id": order_id, "tier": tier}
''', "")}
shutil.copytree("releases/2.0.0", "releases/2.0.1", ignore=shutil.ignore_patterns("__pycache__"))
init = Path("releases/2.0.1/helpdesk/__init__.py"); init.write_text(init.read_text().replace("2.0.0", "2.0.1"))
planner = Path("releases/2.0.1/helpdesk/planner.py"); text = planner.read_text()
for place, (asked, differed) in places.items():
    if differed == 0:
        old, new = CUTS[place]
        assert text.count(old) == 1, place
        text = text.replace(old, new)
        print("removed", place)
planner.write_text(text)
tools = [x for t in ("lookup_order", "lookup_customer", "check_return_policy", "get_shipping_status", "issue_refund", "escalate_to_human") for x in ("--tool", t)]
print("registered", cli("agent", "version", "register", "helpdesk-agent", "--display-version", "2.0.1", "--command", "python -m helpdesk.agent", "--working-dir", "/app/releases/2.0.1", *tools).get("ok"))
sample = list({s["id"]: s for s in RECORDED[::6] + [s for s in RECORDED if kind(s) == "refund"][:10]}.values())[:80]
replays = experiment("fewer-lookups", cohort("fewer-lookups-check", sample), "helpdesk-agent@2")
results = {s["id"]: s for s in asyncio.run(_sessions([r["result_session_id"] for r in replays if r.get("result_session_id")]))}
recorded = {s["id"]: s for s in sample}
same = sum(1 for r in replays if r.get("result_session_id") and results[r["result_session_id"]]["answer"] == recorded[r["baseline_session_id"]]["answer"])
print(len(replays), "replays;", sum(r["status"] == "completed" for r in replays), "completed;", same, "with the recorded answer")
PY
