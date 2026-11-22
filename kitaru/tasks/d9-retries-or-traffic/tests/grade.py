"""Grader for D9. Two cohorts, one per cost spike, and /app/answer.json with each spike's date and cause. Spike 1 is
the order-service outage (conversations with three or more timed-out lookups that day); spike 2 is the promotion's extra
conversations. Runs none of the agent's code."""
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
    answer = read_answer_file("/app/answer.json") or {}
    result: dict = {}
    for number in (1, 2):
        name, fact = f"cost-spike-{number}", truth["facts"][f"cost_spike_{number}"]
        given = answer.get(name) if isinstance(answer.get(name), dict) else {}
        score = score_cohort(name, set(truth["planted"][f"cost_spike_{number}"]))
        score |= {"date_ok": given.get("date") == fact["date"], "cause_ok": given.get("cause") == fact["cause"], "answer": {k: str(given.get(k))[:40] for k in ("date", "cause")}}
        result[name] = score
    return result | {"reward": int(all(s["ok"] and s["date_ok"] and s["cause_ok"] for s in result.values()))}


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
