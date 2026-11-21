#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Reference: run both checks over the week, 100 conversations per request, link every conversation either one fails, and give the verdict by what the check exists to catch:
# a curt ending of a finished conversation or a second issued refund is `problematic`, an idle timeout is `acceptable`.
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

CLOSINGS = ("Thanks for shopping with Larkspur Goods.", "Is there anything else I can help you with?", "Have a lovely day.")
week = [r for r in ROWS if day(r) >= "2026-07-24"]
refunds = lambda r: [n for n in tools(r, "issue_refund") if n["status"] == "completed"]
def wrong_amount(r):
    digits = re.sub(r"\D", "", reply(r))
    return any(re.sub(r"\D", "", n["inputs"]["amount"]) + "00" in digits for n in refunds(r))
def late(r):
    found = [n for n in tools(r, "lookup_order") if n["status"] == "completed"]
    return bool(refunds(r)) and bool(found) and found[-1]["outputs"]["days_since_delivery"] > 30
twice = lambda r: len(refunds(r)) > 1
no_courtesy = lambda r: not reply(r).rstrip().endswith(CLOSINGS)
curt = lambda r: no_courtesy(r) and r["session"]["metadata"].get("end_reason") == "resolved"

def investigate(name, rows, verdict="problematic"):
    args = [x for r in rows for x in ("--session", sid(r), "--session-question", sid(r) + ":mistake=What did the assistant get wrong?")]
    made = cli("investigation", "create", name, "--agent", "returns-agent", "--description", "Conversations from 24 to 30 July to read", *args)
    for r in rows if verdict else []:
        cli("investigation", "session", "verdict", made["item"]["id"], sid(r), verdict)
    print(name, made.get("ok"), len(rows), verdict)
    return made["item"]["id"]

def evaluate(rows, evaluator):
    """Run one evaluator version over the rows, 100 per request, and return the ids it failed."""
    for start in range(0, len(rows), 100):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("".join(sid(r) + "\n" for r in rows[start:start + 100]))
        cli("session", "evaluate", "--sessions-file", f.name, "--evaluator", evaluator, "--wait", "--timeout", "900")
    name, version = evaluator.split("@")
    failed, cursor = set(), None
    while True:
        page = cli("evaluation", "list", "--size", "1000", *(["--cursor", cursor] if cursor else []))
        failed |= {e["session_id"] for e in page["items"] if e.get("evaluator_name") == name and str(e.get("evaluator_version")) == version and e.get("passed") is False}
        cursor = (page.get("page") or {}).get("next_cursor")
        if not cursor:
            return failed

def triage(rows, verdict_of, name="week-30-triage"):
    args = [x for r in rows for x in ("--session", sid(r), "--session-question", sid(r) + ":check=Is the check right about this conversation?")]
    made = cli("investigation", "create", name, "--agent", "returns-agent", "--description", "What the team's checks flag, 24 to 30 July", *args)
    for r in rows:
        if verdict_of(r):
            cli("investigation", "session", "verdict", made["item"]["id"], sid(r), verdict_of(r))
    print(name, made.get("ok"), len(rows))

WEEK = week
polite, once = evaluate(WEEK, "polite-closing@1"), evaluate(WEEK, "refund-issued-once@2")
flagged = [r for r in WEEK if sid(r) in polite | once]
right = lambda r: (sid(r) in once and twice(r)) or (sid(r) in polite and curt(r))
triage(flagged, lambda r: "problematic" if right(r) else "acceptable")
PY
