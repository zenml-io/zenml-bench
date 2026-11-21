"""Grader for F8. Checks that the three existing releases are untouched, that the newest agent version is 2.0.1 run from its own
directory, and that the finance service received no call from the agent's work. Looks for the evidence: one cohort version that
holds the recorded refunds of one item (at least 95 in 100 of them, nothing that is not a request for one item), with a completed
experiment run against version 2 and one against version 3, every result of both judged by `refund-amount`. Then it serves
hidden orders, runs hidden refund requests through the newest version, and compares what the finance service was asked to pay
with what each customer was owed."""
import json
import sys
from pathlib import Path

from kitaru_checks import KitaruError, finance_rows, kitaru, list_all, repo_changed, run_assistant, serve_orders, start_grader_worker

FIXTURES = Path(__file__).parent / "fixtures"
BEFORE, AGENT, EVALUATOR, SHARE = "/etc/kitaru-bench/helpdesk.json", "helpdesk-agent", "refund-amount", 0.95
UNITS = {"USD": 100, "EUR": 100, "GBP": 100, "JPY": 1}


def evidence(before: dict, truth: dict) -> dict:
    """The best cohort version that both candidates were run over."""
    recorded = {i: name for name, i in before["sessions"].items()}
    asked_one = {n for n, r in truth["requests"].items() if r["kind"] == "partial"}
    paid_one = {n for n in asked_one if truth["requests"][n]["refunded"]}
    judged = {e["session_id"] for e in list_all("evaluation", "list") if e.get("evaluator_name") == EVALUATOR and e.get("passed") is not None}
    by_run: dict[str, list[dict]] = {}
    for r in list_all("replay", "list"):
        if r.get("experiment_run_id"):
            by_run.setdefault(r["experiment_run_id"], []).append(r)
    by_cohort: dict[str, dict[str, bool]] = {}
    for run_id, replays in by_run.items():
        run = kitaru("experiment", "run", "get", run_id, check=False).get("item") or {}
        run = run.get("run", run)
        who = {before["versions"]["2.0.1-ana"]: "ana", before["versions"]["2.0.1-ben"]: "ben"}.get(run.get("agent_version_id"))
        good = run.get("status") == "completed" and all(r["status"] == "completed" and r.get("result_session_id") in judged for r in replays)
        if who and run.get("cohort_version_id"):
            slot = by_cohort.setdefault(run["cohort_version_id"], {"ana": False, "ben": False, "replays": len(replays)})
            slot[who] = slot[who] or good
    best: dict = {"cohort_versions_with_a_candidate_run": len(by_cohort), "ok": False}
    for version_id, slot in by_cohort.items():
        members = {recorded.get(s["id"], s["id"]) for s in list_all("session", "list", "--filter", json.dumps({"field": "cohort_version_id", "op": "eq", "value": version_id}))}
        summary = {"members": len(members), "refunds_of_one_item": len(members & paid_one), "of": len(paid_one), "not_a_request_for_one_item": len(members - asked_one),
                   "completed_run_against_version_2": slot["ana"], "completed_run_against_version_3": slot["ben"]}
        summary["ok"] = slot["ana"] and slot["ben"] and not summary["not_a_request_for_one_item"] and len(members & paid_one) >= SHARE * len(paid_one) and slot["replays"] == len(members)
        if summary["ok"] or "members" not in best:
            best |= summary
        if summary["ok"]:
            break
    return best


def grade() -> dict:
    before = json.loads(Path(BEFORE).read_text())
    truth = json.loads((FIXTURES / "ground_truth.json").read_text())
    agent = kitaru("agent", "get", AGENT, check=False)
    if not agent.get("ok") or agent["item"]["id"] != before["agent_id"]:
        return {"reward": 0, "reason": f"{AGENT} is not the agent that was registered"}
    newest = sorted(list_all("agent", "version", "list", AGENT), key=lambda v: v["version"])[-1]
    spec = newest.get("run_spec") or {}
    metrics: dict = {"existing_releases_untouched": not repo_changed(before["head"], "releases/2.0.0", "releases/2.0.1-ana", "releases/2.0.1-ben"),
                     "newest_version": {"version": newest["version"], "display_version": newest.get("display_version"), "working_dir": spec.get("working_dir")},
                     "new_refunds": finance_rows("refunds") - before["refund_rows"], "new_escalations": finance_rows("escalations") - before["escalation_rows"]}
    metrics["version_ok"] = newest["version"] >= 4 and newest.get("display_version") == "2.0.1" and (spec.get("working_dir") or "").rstrip("/") == "/app/releases/2.0.1" and bool(spec.get("command"))
    metrics["evidence"] = evidence(before, truth)
    if not (metrics["existing_releases_untouched"] and metrics["version_ok"]):
        return metrics | {"reward": 0, "reason": "an existing release was changed, or the newest version is not 2.0.1 run from /app/releases/2.0.1"}

    start_grader_worker()  # stops everything the agent's user runs and locks the grader's files
    hidden = [r for r in json.loads((FIXTURES / "hidden_requests.json").read_text()) if r["kind"] in ("refund", "partial")]
    serve_orders(str(FIXTURES / "hidden_services_data.json"), "grader-new")
    start = finance_rows("refunds")
    sessions = run_assistant(hidden, "/app/releases/2.0.1", before["agent_id"], newest["id"], "new", workers=3)
    paid = {}
    for line in open("/var/lib/helpdesk-finance/refunds.jsonl").read().splitlines()[start:]:
        row = json.loads(line)
        paid.setdefault(row.get("order_id"), []).append(round(float(row.get("amount", -1)) * UNITS.get(row.get("currency"), 1)))
    wrong = {"did_not_run": [], "one_item": [], "whole_order": []}
    for r in hidden:
        e = r["expected"]
        owed = [e["right_refund_minor"] if r["kind"] == "partial" else e["refund_minor"]] if e["refunded"] else []
        if r["id"] not in sessions:
            wrong["did_not_run"].append(r["id"])
        elif paid.get(r["orders"][0], []) != owed:
            wrong["one_item" if r["kind"] == "partial" else "whole_order"].append(r["id"])
    metrics["hidden"] = {"requests": len(hidden), "for_one_item": sum(r["kind"] == "partial" for r in hidden), **{f"wrong_{k}": len(v) for k, v in wrong.items()}, "examples": {k: v[:5] for k, v in wrong.items() if v}}
    metrics["hidden_ok"] = not any(wrong.values())
    metrics["reward"] = int(metrics["evidence"]["ok"] and metrics["hidden_ok"] and metrics["new_refunds"] == 0 and metrics["new_escalations"] == 0)
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
