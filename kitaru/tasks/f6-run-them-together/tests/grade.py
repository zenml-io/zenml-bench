"""Grader for F6. Checks that release 2.0.0 is untouched, that the newest agent version is 2.0.1 run from its own directory, and
that the finance service received no call from the agent's work. Then it serves hidden orders from the order service and runs the
hidden requests, one conversation at a time, through release 2.0.0; serves the same orders again from an empty memory and runs
them through the newest version. Per request, from the tool calls Kitaru recorded: the same answer, the same calls with the same
arguments, the order and the customer read at the same time when the message gives the account, and at most three quarters of
2.0.0's time for a message about four or more orders. Over the whole run: the same payments, and no lookup refused (the order
service serves four at a time; the hidden messages ask about up to six orders)."""
import json
import sys
from pathlib import Path

from kitaru_checks import KitaruError, conversations, finance_rows, kitaru, list_all, repo_changed, run_assistant, serve_orders, start_grader_worker

FIXTURES = Path(__file__).parent / "fixtures"
BEFORE, AGENT = "/etc/kitaru-bench/helpdesk.json", "helpdesk-agent"
MANY_ORDERS, SHARE_OF_OLD_TIME = 4, 0.75


def ledger(kind: str, start: int) -> list[tuple]:
    rows = [json.loads(line) for line in open(f"/var/lib/helpdesk-finance/{kind}.jsonl").read().splitlines()[start:]]
    return sorted((r.get("order_id"), r.get("amount"), r.get("currency"), r.get("reason")) for r in rows)


def keys(calls: list[dict]) -> list[str]:
    return sorted(c["tool"] + " " + json.dumps(c["inputs"], sort_keys=True) for c in calls)


def span(calls: list[dict]) -> float:
    return max(c["end"] for c in calls) - min(c["start"] for c in calls) if calls else 0.0


def together(calls: list[dict], a: str, b: str) -> bool:
    """True when the first call of tool `a` and the first call of tool `b` overlap in time."""
    first = {t: next((c for c in calls if c["tool"] == t), None) for t in (a, b)}
    return all(first.values()) and first[a]["start"] < first[b]["end"] and first[b]["start"] < first[a]["end"]


def grade() -> dict:
    before = json.loads(Path(BEFORE).read_text())
    agent = kitaru("agent", "get", AGENT, check=False)
    if not agent.get("ok") or agent["item"]["id"] != before["agent_id"]:
        return {"reward": 0, "reason": f"{AGENT} is not the agent that was registered"}
    newest = sorted(list_all("agent", "version", "list", AGENT), key=lambda v: v["version"])[-1]
    spec = newest.get("run_spec") or {}
    metrics: dict = {"release_2_0_0_untouched": not repo_changed(before["head"], "releases/2.0.0"),
                     "newest_version": {"version": newest["version"], "display_version": newest.get("display_version"), "working_dir": spec.get("working_dir")},
                     "new_refunds": finance_rows("refunds") - before["refund_rows"], "new_escalations": finance_rows("escalations") - before["escalation_rows"]}
    metrics["version_ok"] = newest["version"] >= 2 and newest.get("display_version") == "2.0.1" and (spec.get("working_dir") or "").rstrip("/") == "/app/releases/2.0.1" and bool(spec.get("command"))
    if not (metrics["release_2_0_0_untouched"] and metrics["version_ok"]):
        return metrics | {"reward": 0, "reason": "release 2.0.0 was changed, or the newest version is not 2.0.1 run from /app/releases/2.0.1"}

    start_grader_worker()  # stops everything the agent's user runs and locks the grader's files
    hidden = json.loads((FIXTURES / "hidden_requests.json").read_text())
    data = str(FIXTURES / "hidden_services_data.json")
    runs = {}
    for tag, directory, version in (("old", "/app/releases/2.0.0", before["versions"]["2.0.0"]), ("new", "/app/releases/2.0.1", newest["id"])):
        log = serve_orders(data, f"grader-{tag}")
        refunds, escalations = finance_rows("refunds"), finance_rows("escalations")
        sessions = run_assistant(hidden, directory, before["agent_id"], version, tag, workers=1)
        runs[tag] = {"sessions": sessions, "paid": ledger("refunds", refunds), "escalated": ledger("escalations", escalations),
                     "refused": sum(json.loads(line)["status"] == 429 for line in open(log).read().splitlines())}
    stored = conversations([i for t in runs for k, i in runs[t]["sessions"].items() if not k.startswith("failed:")])
    wrong: dict[str, list[str]] = {"did_not_run": [], "answer": [], "calls_differ": [], "order_and_customer_not_together": [], "many_orders_not_faster": []}
    shares = []
    for r in hidden:
        old, new = (runs[t]["sessions"].get(r["id"]) for t in ("old", "new"))
        if not old or not new:
            wrong["did_not_run"].append(r["id"])
            continue
        old, new = stored[old], stored[new]
        if old["answer"] != new["answer"] or new["answer"] is None:
            wrong["answer"].append(r["id"])
        if keys(old["calls"]) != keys(new["calls"]):
            wrong["calls_differ"].append(r["id"])
        if r["kind"] in ("refund", "dispute") and not r["guest"] and not together(new["calls"], "lookup_order", "lookup_customer"):
            wrong["order_and_customer_not_together"].append(r["id"])
        if r["kind"] == "status" and len(r["orders"]) >= MANY_ORDERS:
            shares.append(round(span(new["calls"]) / span(old["calls"]), 2))
            if shares[-1] > SHARE_OF_OLD_TIME:
                wrong["many_orders_not_faster"].append(r["id"])
    metrics["hidden"] = {"requests": len(hidden), "same_payments": runs["old"]["paid"] == runs["new"]["paid"], "same_escalations": runs["old"]["escalated"] == runs["new"]["escalated"],
                         "lookups_refused": runs["new"]["refused"], "lookups_refused_for_2_0_0": runs["old"]["refused"], "share_of_old_time_for_many_orders": shares,
                         **{k: len(v) for k, v in wrong.items()}, "examples": {k: v[:5] for k, v in wrong.items() if v}}
    metrics["hidden_ok"] = metrics["hidden"]["same_payments"] and metrics["hidden"]["same_escalations"] and runs["new"]["refused"] == 0 and not any(wrong.values())
    metrics["reward"] = int(metrics["hidden_ok"] and metrics["new_refunds"] == 0 and metrics["new_escalations"] == 0)
    return metrics


if __name__ == "__main__":
    try:
        result = grade()
    except KitaruError as e:
        result = {"reward": 0, "reason": f"grader could not finish: {e}"}
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/metrics.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1), file=sys.stderr)
    print(result["reward"])
