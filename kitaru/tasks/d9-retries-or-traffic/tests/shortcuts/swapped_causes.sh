#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the right cohorts and days with the two causes the wrong way round. Must score 0.
python3 - <<'PY'
import asyncio, json, re, subprocess, tempfile
from collections import defaultdict
from decimal import Decimal
from kitaru.client import KitaruAPIClient

async def _load():
    async with KitaruAPIClient() as client:
        ids = [s.id async for s in client.sessions.iter()]
        gate = asyncio.Semaphore(8)
        async def one(i):
            async with gate:
                return (await client.sessions.get_with_nodes(i)).model_dump(mode="json")
        return await asyncio.gather(*(one(i) for i in ids))

ROWS = sorted(asyncio.run(_load()), key=lambda r: r["session"]["started_at"])
sid = lambda r: r["session"]["id"]
day = lambda r: r["session"]["started_at"][:10]
tools = lambda r, name: [n for n in r["nodes"] if n["node_type"] == "tool_call" and n["name"] == name]
llm = lambda r: [n for n in r["nodes"] if n["node_type"] == "llm_call"]
failed_lookups = lambda r: sum(n["status"] == "failed" for n in tools(r, "lookup_order"))
reply = lambda r: (r["session"].get("outputs") or r["nodes"][0].get("outputs") or {}).get("reply", "")

def cli(*args):
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    return json.loads(out.stdout or out.stderr)

def cohort(name, rows):
    """Create the cohort, or give an existing one a new version holding exactly these sessions."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("".join(sid(r) + "\n" for r in rows))
    made = cli("cohort", "create", name, "--agent", "returns-agent", "--sessions-file", f.name)
    if made.get("ok"):
        return print(name, "created with", len(rows))
    number = cli("cohort", "get", name)["item"]["latest_version"]
    current = set()
    if number:
        cursor = None
        while True:
            page = cli("session", "list", "--cohort", f"{name}@{number}", "--size", "1000", *(["--cursor", cursor] if cursor else []))
            current |= {s["id"] for s in page["items"]}
            cursor = (page.get("page") or {}).get("next_cursor")
            if not cursor:
                break
    wanted = {sid(r) for r in rows}
    add, remove = sorted(wanted - current), sorted(current - wanted)
    # one flag per session: `--add-session A B` is refused ("Unused Tokens") although the help shows `UUID...`
    out = cli("cohort", "version", "create", name, *(x for i in add for x in ("--add-session", i)), *(x for i in remove for x in ("--remove-session", i)))
    print(name, "new version:", out.get("ok"), "+", len(add), "-", len(remove))

def answer(obj):
    open("/app/answer.json", "w").write(json.dumps(obj, indent=1) + "\n")

cost = defaultdict(float)
for r in ROWS: cost[day(r)] += float(r["session"]["cost"])
first, second = sorted(sorted(cost, key=cost.get)[-2:])
on = lambda d: [r for r in ROWS if day(r) == d]
def explain(d, loose=False):
    """The conversations behind the day's extra cost, and the cause."""
    retried = [r for r in on(d) if failed_lookups(r) >= (1 if loose else 3)]
    if len(retried) > 0.3 * len(on(d)):
        return retried, "retry_loop"
    return [r for r in on(d) if r["session"]["metadata"].get("campaign")], "traffic_increase"
out = {}
for name, d in (("cost-spike-1", first), ("cost-spike-2", second)):
    rows, cause = explain(d)
    cohort(name, rows)
    out[name] = {"date": d, "cause": "traffic_increase" if cause == "retry_loop" else "retry_loop"}
answer(out)
PY
