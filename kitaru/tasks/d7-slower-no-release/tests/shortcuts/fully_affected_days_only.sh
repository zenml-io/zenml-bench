#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: only the days on which every conversation was affected; misses the partial days before. Must score 0.
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

swapped = [r for r in ROWS if any(n.get("model") != n.get("requested_model") for n in llm(r))]
per_day, hit = defaultdict(int), defaultdict(int)
for r in ROWS: per_day[day(r)] += 1
for r in swapped: hit[day(r)] += 1
full = {d for d in hit if hit[d] == per_day[d]}
cohort("slower-replies", [r for r in swapped if day(r) in full])
answer({"cause": "served_model_changed", "first_affected_day": min(full)})
PY
