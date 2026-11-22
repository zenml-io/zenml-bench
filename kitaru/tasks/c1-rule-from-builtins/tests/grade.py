"""Grader for C1. Reads the evaluations Kitaru stored and checks them against the rule, session by
session. Runs none of the agent's code. Writes /logs/verifier/metrics.json and prints the reward.
"""
import json
import subprocess
import sys
from pathlib import Path

from kitaru_checks import KitaruError, all_evaluations, kitaru, lock_grader_files, sessions_by_external_id

WEEK_START = "2026-07-24T00:00:00"
MAX_CALLS = 3
OUTSIDE_ALLOWED = 50


def grade() -> dict:
    lock_grader_files()
    subprocess.run(["/opt/kitaru-bench/start.sh", "--no-worker"], capture_output=True)
    truth = json.loads((Path(__file__).parent / "fixtures" / "ground_truth.json").read_text())["per_session"]
    ids = sessions_by_external_id()
    if set(ids) != set(truth):
        return {"reward": 0, "reason": f"the workspace holds {len(ids)} history sessions, expected {len(truth)}"}
    in_week = {ids[x] for x, t in truth.items() if t["started_at"] >= WEEK_START}
    should_pass = {ids[x]: t["lookups"] <= MAX_CALLS for x, t in truth.items()}
    builtin = [e for e in all_evaluations() if (e.get("evaluator_name") or "").startswith("kitaru/")]
    verdict: dict[str, bool] = {}  # per session: the most recent built-in result that states pass or fail
    for e in builtin:
        if e.get("passed") is not None:
            verdict[e["session_id"]] = e["passed"]
    correct = sum(1 for s in in_week if verdict.get(s) is should_pass[s])
    outside = {e["session_id"] for e in builtin} - in_week
    metrics = {"in_week": len(in_week), "with_verdict": len(in_week & set(verdict)), "correct": correct,
               "wrong": sum(1 for s in in_week if s in verdict and verdict[s] is not should_pass[s]),
               "rule_breakers_in_week": sum(1 for s in in_week if not should_pass[s]), "outside_week_evaluated": len(outside),
               "builtin_evaluators_used": sorted({e["evaluator_name"] for e in builtin})}
    agent = kitaru("agent", "get", "returns-agent", check=False)
    metrics["collateral_ok"] = bool(agent.get("ok")) and agent["item"]["latest_version"] == 3
    metrics["reward"] = int(correct == len(in_week) and len(outside) <= OUTSIDE_ALLOWED and metrics["collateral_ok"])
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
