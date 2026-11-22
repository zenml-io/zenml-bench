"""Grader for F4. An experiment run of version 3 over the cohort `recorded-refunds` must have completed with all 58 conversations
replayed and passing `refund-amount`; the finance service must have received no call; and in that run the refund tool must not
have been able to run live (not `passthrough`, and no `on_miss: passthrough`). The run fails as first set up because the fixed
release asks `issue_refund` for another amount than the recording holds. Runs none of the agent's code."""
import json
import subprocess
import sys
from pathlib import Path

from kitaru_checks import KitaruError, finance_rows, kitaru, list_all, lock_grader_files, repo_changed

BEFORE, AGENT, EVALUATOR = "/etc/kitaru-bench/helpdesk.json", "helpdesk-agent", "refund-amount"


def could_run_live(policy: dict, tool: str) -> bool:
    rule = (policy.get("tools") or {}).get(tool) or policy.get("default") or {"type": "passthrough"}
    return rule.get("type") == "passthrough" or rule.get("on_miss") == "passthrough"


def grade() -> dict:
    before = json.loads(Path(BEFORE).read_text())
    start = before["f4"]
    agent = kitaru("agent", "get", AGENT, check=False)
    cohort = kitaru("cohort", "get", "recorded-refunds", check=False)
    metrics: dict = {"agent_ok": bool(agent.get("ok")) and agent["item"]["id"] == before["agent_id"] and agent["item"]["latest_version"] == 3,
                     "cohort_ok": bool(cohort.get("ok")) and cohort["item"]["latest_version"] == 1,
                     "repository_unchanged": not repo_changed(before["head"], "releases", "data", "evaluators"),
                     "new_refunds": finance_rows("refunds") - before["refund_rows"], "new_escalations": finance_rows("escalations") - before["escalation_rows"]}
    replays: dict[str, list[dict]] = {}
    for r in list_all("replay", "list"):
        if r.get("experiment_run_id") and r["experiment_run_id"] != start["failed_run_id"]:
            replays.setdefault(r["experiment_run_id"], []).append(r)
    verdicts: dict[str, bool] = {}
    for e in sorted(list_all("evaluation", "list"), key=lambda e: e["created"]):
        if e.get("evaluator_name") == EVALUATOR and e.get("passed") is not None:
            verdicts[e["session_id"]] = e["passed"]
    best: dict = {"new_runs": len(replays), "ok": False}
    for run_id, rows in replays.items():
        run = kitaru("experiment", "run", "get", run_id, check=False).get("item") or {}
        run = run.get("run", run)
        summary = {"status": run.get("status"), "version_3": run.get("agent_version_id") == start["version_3_id"], "right_cohort": run.get("cohort_version_id") == start["cohort_version_id"],
                   "replays": len(rows), "replays_completed": sum(r["status"] == "completed" for r in rows),
                   "results_passing": sum(verdicts.get(r.get("result_session_id") or "") is True for r in rows),
                   "refund_tool_could_run_live": any(could_run_live(r.get("tool_policy") or {}, "issue_refund") or could_run_live(r.get("tool_policy") or {}, "escalate_to_human") for r in rows)}
        summary["ok"] = (summary["status"] == "completed" and summary["version_3"] and summary["right_cohort"] and summary["replays"] == start["cohort_size"]
                         and summary["replays_completed"] == start["cohort_size"] and summary["results_passing"] == start["cohort_size"] and not summary["refund_tool_could_run_live"])
        if summary["ok"] or not best.get("status"):
            best = {"new_runs": len(replays), **summary}
        if summary["ok"]:
            break
    metrics["run"] = best
    metrics["reward"] = int(metrics["agent_ok"] and metrics["cohort_ok"] and metrics["repository_unchanged"] and best["ok"] and metrics["new_refunds"] == 0 and metrics["new_escalations"] == 0)
    return metrics


if __name__ == "__main__":
    try:
        lock_grader_files()
        subprocess.run(["/opt/kitaru-bench/start.sh", "--no-worker"], capture_output=True)
        result = grade()
    except KitaruError as e:
        result = {"reward": 0, "reason": f"grader could not finish: {e}"}
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/metrics.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1), file=sys.stderr)
    print(result["reward"])
