"""Grader for F5. Checks that release 2.0.0 is untouched, that the newest agent version is 2.0.1 run from its own directory, and
that the finance service received no call from the agent's work. Then it serves hidden orders from the order service, runs the
hidden requests through release 2.0.0, serves the same orders again from an empty memory, and runs them through the newest
version. Per request: the same answer, the same payments, and exactly 2.0.0's lookups minus the second asks at the three places
that never return anything new in the recorded history (an order with several items read again in a status request, the
customer read again before a dispute is escalated, the policy checked again before a refund is refused)."""
import json
import sys
from pathlib import Path

from kitaru_checks import KitaruError, conversations, finance_rows, kitaru, list_all, repo_changed, run_assistant, serve_orders, start_grader_worker

FIXTURES = Path(__file__).parent / "fixtures"
BEFORE, AGENT = "/etc/kitaru-bench/helpdesk.json", "helpdesk-agent"
WASTE = {("status", "lookup_order"), ("dispute", "lookup_customer"), ("refund", "check_return_policy")}


def ledger(kind: str, start: int) -> list[tuple]:
    rows = [json.loads(line) for line in open(f"/var/lib/helpdesk-finance/{kind}.jsonl").read().splitlines()[start:]]
    return sorted((r.get("order_id"), r.get("amount"), r.get("currency"), r.get("reason")) for r in rows)


def lookups_the_rule_leaves(kind: str, calls: list[dict]) -> list[str]:
    """Release 2.0.0's calls in one conversation, without the second asks the rule removes."""
    answered, keep = set(), []
    for c in calls:
        key = c["tool"] + " " + json.dumps(c["inputs"], sort_keys=True)
        if key in answered and (kind, c["tool"]) in WASTE:
            continue
        if "error" not in (c["outputs"] or {}):
            answered.add(key)
        keep.append(key)
    return sorted(keep)


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
        serve_orders(data, f"grader-{tag}")
        refunds, escalations = finance_rows("refunds"), finance_rows("escalations")
        sessions = run_assistant(hidden, directory, before["agent_id"], version, tag, workers=3)
        runs[tag] = {"sessions": sessions, "paid": ledger("refunds", refunds), "escalated": ledger("escalations", escalations)}
    wrong: dict[str, list[str]] = {"did_not_run": [], "answer": [], "lookups_missing": [], "lookups_too_many": []}
    stored = conversations([i for t in runs for k, i in runs[t]["sessions"].items() if not k.startswith("failed:")])
    for r in hidden:
        old, new = (runs[t]["sessions"].get(r["id"]) for t in ("old", "new"))
        if not old or not new:
            wrong["did_not_run"].append(r["id"])
            continue
        old, new = stored[old], stored[new]
        if old["answer"] != new["answer"] or new["answer"] is None:
            wrong["answer"].append(r["id"])
        want = lookups_the_rule_leaves(r["kind"], old["calls"])
        have = sorted(c["tool"] + " " + json.dumps(c["inputs"], sort_keys=True) for c in new["calls"])
        if any(have.count(k) < want.count(k) for k in set(want)):
            wrong["lookups_missing"].append(r["id"])
        if any(have.count(k) > want.count(k) for k in set(have)):
            wrong["lookups_too_many"].append(r["id"])
    metrics["hidden"] = {"requests": len(hidden), "same_payments": runs["old"]["paid"] == runs["new"]["paid"], "same_escalations": runs["old"]["escalated"] == runs["new"]["escalated"],
                         "refunds_paid_by_2_0_0": len(runs["old"]["paid"]), **{k: len(v) for k, v in wrong.items()}, "examples": {k: v[:5] for k, v in wrong.items() if v}}
    metrics["hidden_ok"] = metrics["hidden"]["same_payments"] and metrics["hidden"]["same_escalations"] and not any(wrong.values())
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
