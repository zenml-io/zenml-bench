"""Grader for F7. Checks the cohort `low-effort-safe` against the answer key (which recorded conversations end the same way at
reasoning effort low): none that ends differently, nothing that is not a recorded conversation, and at least 95 in 100 of those
that do end the same way. Then looks for the proof: a completed experiment run over that cohort's latest version, against
version 1, whose replays all carry the low-effort override and whose result conversations all end with the recorded answer.
The assistant's code must be untouched and the finance service must have received no call."""
import json
import sys
from pathlib import Path

from kitaru_checks import KitaruError, conversations, finance_rows, kitaru, list_all, repo_changed

FIXTURES = Path(__file__).parent / "fixtures"
BEFORE, COHORT, SHARE = "/etc/kitaru-bench/helpdesk.json", "low-effort-safe", 0.95


def proof(version_id: str, size: int, agent_version_id: str) -> dict:
    """The best experiment run over the cohort version: completed, every replay overridden to low effort, every result ending as recorded."""
    by_run: dict[str, list[dict]] = {}
    for r in list_all("replay", "list"):
        if r.get("experiment_run_id"):
            by_run.setdefault(r["experiment_run_id"], []).append(r)
    best: dict = {"runs_over_this_cohort_version": 0, "ok": False}
    for run_id, replays in by_run.items():
        run = kitaru("experiment", "run", "get", run_id, check=False).get("item") or {}
        run = run.get("run", run)
        if run.get("cohort_version_id") != version_id:
            continue
        best["runs_over_this_cohort_version"] += 1
        done = [r for r in replays if r["status"] == "completed" and r.get("result_session_id")]
        stored = conversations([i for r in done for i in (r["baseline_session_id"], r["result_session_id"])])
        summary = {"status": run.get("status"), "against_version_1": run.get("agent_version_id") == agent_version_id, "replays": len(replays), "completed": len(done),
                   "with_low_effort_override": sum(((r.get("override") or {}).get("model_params") or {}).get("reasoning_effort") == "low" for r in replays),
                   "end_as_recorded": sum(stored[r["baseline_session_id"]]["answer"] == stored[r["result_session_id"]]["answer"] is not None for r in done)}
        summary["ok"] = (summary["status"] == "completed" and summary["against_version_1"] and len(replays) == size == summary["completed"] == summary["with_low_effort_override"] == summary["end_as_recorded"])
        if summary["ok"] or "status" not in best:
            best |= summary
        if summary["ok"]:
            break
    return best


def grade() -> dict:
    before = json.loads(Path(BEFORE).read_text())
    truth = json.loads((FIXTURES / "ground_truth.json").read_text())
    differ = set(truth["not_same_at_low_effort"])
    same = set(truth["requests"]) - differ
    metrics: dict = {"new_refunds": finance_rows("refunds") - before["refund_rows"], "new_escalations": finance_rows("escalations") - before["escalation_rows"],
                     "assistant_untouched": not repo_changed(before["head"], "releases")}
    cohort = kitaru("cohort", "get", COHORT, check=False)
    if not cohort.get("ok") or not cohort["item"].get("latest_version"):
        return metrics | {"reward": 0, "reason": f"no cohort named {COHORT} with a version"}
    version = kitaru("cohort", "version", "get", f"{COHORT}@{cohort['item']['latest_version']}")["item"]
    recorded = {i: name for name, i in before["sessions"].items()}
    members = [s["id"] for s in list_all("session", "list", "--filter", json.dumps({"field": "cohort_version_id", "op": "eq", "value": version["id"]}))]
    names = {recorded[i] for i in members if i in recorded}
    metrics["cohort"] = {"members": len(members), "not_recorded_conversations": sum(i not in recorded for i in members), "end_differently": len(names & differ), "end_the_same": len(names & same),
                         "of": len(same), "share_found": round(len(names & same) / len(same), 4), "examples_that_end_differently": sorted(names & differ)[:8]}
    metrics["cohort_ok"] = not metrics["cohort"]["not_recorded_conversations"] and not metrics["cohort"]["end_differently"] and metrics["cohort"]["share_found"] >= SHARE
    metrics["proof"] = proof(version["id"], len(members), before["versions"]["2.0.0"])
    metrics["reward"] = int(metrics["assistant_untouched"] and metrics["cohort_ok"] and metrics["proof"]["ok"] and metrics["new_refunds"] == 0 and metrics["new_escalations"] == 0)
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
