"""Grader for D7. The cohort `slower-replies` must hold the conversations whose model calls were served by a
different model than the one requested, and /app/answer.json must name that cause and the first affected day.
Runs none of the agent's code."""
import json
import subprocess
import sys
from pathlib import Path

from kitaru_checks import KitaruError, kitaru, lock_grader_files, read_answer_file, score_cohort, sessions_by_external_id


def workspace_intact(truth: dict) -> str | None:
    """None when the history and the agent's releases are as the task started; otherwise what changed."""
    ids = sessions_by_external_id()
    if set(ids) != set(truth["per_session"]):
        return f"the workspace holds {len(ids)} history sessions, expected {len(truth['per_session'])}"
    agent = kitaru("agent", "get", "returns-agent", check=False)
    if not agent.get("ok") or agent["item"]["latest_version"] != 3:
        return "the returns agent's releases were changed"
    return None


def grade(truth: dict) -> dict:
    score = score_cohort("slower-replies", set(truth["planted"]["model_swap"]))
    answer = read_answer_file("/app/answer.json") or {}
    score["cause_ok"] = answer.get("cause") == "served_model_changed"
    score["day_ok"] = answer.get("first_affected_day") == truth["facts"]["model_swap_first_day"]
    score["answer"] = {k: str(answer.get(k))[:40] for k in ("cause", "first_affected_day")}
    return score | {"reward": int(score["ok"] and score["cause_ok"] and score["day_ok"])}


if __name__ == "__main__":
    try:
        lock_grader_files()
        subprocess.run(["/opt/kitaru-bench/start.sh", "--no-worker"], capture_output=True)
        truth = json.loads((Path(__file__).parent / "fixtures" / "ground_truth.json").read_text())
        broken = workspace_intact(truth)
        result = {"reward": 0, "reason": broken} if broken else grade(truth)
    except KitaruError as e:
        result = {"reward": 0, "reason": f"grader could not finish: {e}"}
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/metrics.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1), file=sys.stderr)
    print(result["reward"])
