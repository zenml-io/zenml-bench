"""Grader for C4. Reads the evaluations Kitaru stored: version 2 of `refund-issued-once` must cover
every conversation of release 1.4.1, almost nothing older, and not many times over. Runs none of the
agent's code. Writes /logs/verifier/metrics.json and prints the reward.
"""
import json
import subprocess
import sys
from pathlib import Path

from kitaru_checks import KitaruError, all_evaluations, kitaru, latest_version, lock_grader_files, sessions_by_external_id

EVALUATOR, VERSION, RELEASE = "refund-issued-once", 2, "1.4.1"
OUTSIDE_ALLOWED, MAX_RESULTS = 30, 1400


def grade() -> dict:
    lock_grader_files()
    subprocess.run(["/opt/kitaru-bench/start.sh", "--no-worker"], capture_output=True)
    truth = json.loads((Path(__file__).parent / "fixtures" / "ground_truth.json").read_text())["per_session"]
    ids = sessions_by_external_id()
    if set(ids) != set(truth):
        return {"reward": 0, "reason": f"the workspace holds {len(ids)} history sessions, expected {len(truth)}"}
    in_release = {ids[x] for x, t in truth.items() if t["release"] == RELEASE}
    rows = [e for e in all_evaluations() if e.get("evaluator_name") == EVALUATOR and e.get("evaluator_version") == VERSION]
    covered = {e["session_id"] for e in rows}
    metrics = {"in_release": len(in_release), "covered": len(covered & in_release), "outside_release_evaluated": len(covered - in_release),
               "version_2_results": len(rows), "version_1_results": sum(1 for e in all_evaluations() if e.get("evaluator_name") == EVALUATOR and e.get("evaluator_version") == 1)}
    latest = latest_version("evaluator", EVALUATOR)
    agent = kitaru("agent", "get", "returns-agent", check=False)
    metrics["collateral_ok"] = bool(agent.get("ok")) and agent["item"]["latest_version"] == 3 and latest is not None and latest["version"] == VERSION
    metrics["reward"] = int(in_release <= covered and len(covered - in_release) <= OUTSIDE_ALLOWED and len(rows) <= MAX_RESULTS and metrics["collateral_ok"])
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
