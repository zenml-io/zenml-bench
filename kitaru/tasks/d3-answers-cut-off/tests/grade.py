"""Grader for D3. The cohort `cut-off-answers` must hold the conversations whose final reply hit the token limit (care advice, and the summary a new
patient gets, from 1 July), and /app/answer.json must name the configuration commit that lowered `max_tokens` and the first affected day.
Runs none of the agent's code."""
import json
import subprocess
import sys
from pathlib import Path

from kitaru_checks import KitaruError, kitaru, lock_grader_files, read_answer_file, score_cohort, sessions_by_external_id

BEFORE = "/etc/kitaru-bench/clinic.json"  # written while the image was built; root only


def git(*args: str) -> str:
    return subprocess.run(["git", "-c", "safe.directory=/app", "-C", "/app", *args], capture_output=True, text=True).stdout.strip()


def workspace_intact(truth: dict) -> str | None:
    """None when the history, the agent's releases and the repository are as the task started; otherwise what changed."""
    ids = sessions_by_external_id()
    if set(ids) != set(truth["per_session"]):
        return f"the workspace holds {len(ids)} history sessions, expected {len(truth['per_session'])}"
    agent = kitaru("agent", "get", "booking-agent", check=False)
    if not agent.get("ok") or agent["item"]["latest_version"] != 3:
        return "the booking agent's releases were changed"
    if git("rev-parse", "HEAD") != json.loads(Path(BEFORE).read_text())["head"] or git("status", "--porcelain", "--untracked-files=no"):
        return "the repository's tracked files were changed or something was committed"
    return None

def grade(truth: dict) -> dict:
    score = score_cohort("cut-off-answers", set(truth["planted"]["cut_off"]))
    answer = read_answer_file("/app/answer.json") or {}
    commit, wanted = str(answer.get("commit") or "").strip().lower(), json.loads(Path(BEFORE).read_text())["config_commit"]
    score["commit_ok"] = len(commit) >= 7 and wanted.startswith(commit)
    score["day_ok"] = answer.get("first_affected_day") == truth["facts"]["config_commit_date"]
    score["answer"] = {"commit": commit[:12], "first_affected_day": str(answer.get("first_affected_day"))[:12]}
    return score | {"reward": int(score["ok"] and score["commit_ok"] and score["day_ok"])}


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
