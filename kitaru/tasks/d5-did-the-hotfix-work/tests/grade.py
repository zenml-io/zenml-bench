"""Grader for D5. The cohort `wrong-clinic-after-1-3-0` must hold the 98 conversations served by release 1.3.0 in which `book_appointment` came back
confirmed at another clinic than it was sent. The release fixed the clinic search, not the booking.
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
    score = score_cohort("wrong-clinic-after-1-3-0", set(truth["planted"]["wrong_clinic_after_hotfix"]))
    return score | {"reward": int(score["ok"])}


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
