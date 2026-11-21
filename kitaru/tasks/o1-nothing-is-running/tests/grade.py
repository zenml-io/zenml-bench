"""Grader for O1. Stops everything the agent's user runs, then starts the worker the way the team does: `bash /app/bin/start_worker.sh`,
as user `grader`. Asks Kitaru for new work: evaluations, replays against version 1, replays against an agent version it registers
now, and an import. Passes when the work that was waiting in the image and all the new work except the import complete within
five minutes, the import is still pending at least 90 seconds after it was requested, and the finance service received no call."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from kitaru_checks import SAFE_REPLAY, KitaruError, finance_rows, kitaru, lock_grader_files

FIXTURES = Path(__file__).parent / "fixtures"
BEFORE, AGENT, EVALUATOR = "/etc/kitaru-bench/helpdesk.json", "helpdesk-agent", "refund-once@1"
TOOLS = [x for t in ("lookup_order", "lookup_customer", "check_return_policy", "get_shipping_status", "issue_refund", "escalate_to_human") for x in ("--tool", t)]
DONE = ("completed", "failed", "canceled", "cancelled")


def job_id(response: dict) -> str:
    """The job a request started.  names it only in the commands it suggests next."""
    item = response.get("item") or {}
    found = re.search(r"[0-9a-f]{8}-[0-9a-f-]{27}", " ".join(response.get("next_actions") or []))
    return item.get("job_id") or (found.group() if found else item.get("id"))


def status(kind: str, ref: str) -> str:
    return (kitaru(kind, "get", ref, check=False).get("item") or {}).get("status") or "unknown"


def grade() -> dict:
    before = json.loads(Path(BEFORE).read_text())
    lock_grader_files()
    subprocess.run(["/opt/kitaru-bench/stop.sh", "--workers"], capture_output=True)
    subprocess.run(["pkill", "-KILL", "-u", "agent"], capture_output=True)
    for _ in range(40):
        if subprocess.run(["/opt/kitaru-bench/start.sh", "--no-worker"], capture_output=True).returncode == 0:
            break
        time.sleep(2)
    metrics: dict = {"new_refunds_before_grading": finance_rows("refunds") - before["refund_rows"], "new_escalations_before_grading": finance_rows("escalations") - before["escalation_rows"]}
    log = open("/var/log/kitaru-bench/script-worker.log", "a")
    env = {"HOME": "/home/grader", "PATH": os.environ["PATH"], **{k: v for k, v in os.environ.items() if k.startswith("KITARU_") or k == "DO_NOT_TRACK"}}
    subprocess.Popen(["runuser", "-u", "grader", "--", "env", "-i", *(f"{k}={v}" for k, v in env.items()), "bash", "/app/bin/start_worker.sh"], cwd="/app", stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    live = []
    for _ in range(45):
        live = [w for w in kitaru("worker", "list", "--size", "100")["items"] if w.get("status") == "live"]
        if live:
            break
        time.sleep(2)
    metrics["workers_the_script_started"] = [{"name": w.get("name"), "scope": w.get("scope")} for w in live]
    if not live:
        return metrics | {"reward": 0, "reason": "bin/start_worker.sh started no worker"}

    names = sorted(before["sessions"])
    later = kitaru("agent", "version", "register", AGENT, "--display-version", "2.0.0-later", "--command", "python -m helpdesk.agent", "--working-dir", "/app/releases/2.0.0", *TOOLS)["item"]
    later = later.get("version", later)
    policy = json.dumps(SAFE_REPLAY)
    new = {"replays_against_version_1": [kitaru("replay", "create", before["sessions"][n], "--evaluator", EVALUATOR, "--tool-policy", policy)["item"]["id"] for n in names[200:203]],
           "replays_against_a_later_version": [kitaru("replay", "create", before["sessions"][n], "--evaluator", EVALUATOR, "--agent", f"{AGENT}@{later['version']}", "--tool-policy", policy)["item"]["id"] for n in names[210:213]]}
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("".join(before["sessions"][n] + "\n" for n in names[220:226]))
    evaluation = job_id(kitaru("session", "evaluate", "--sessions-file", f.name, "--evaluator", EVALUATOR))
    asked_import = time.time()
    incoming = job_id(kitaru("session", "import", str(FIXTURES / "import.jsonl"), "--importer", "kitaru/kitaru-jsonl@latest", "--agent", f"{AGENT}@1", "--media-type", "application/x-ndjson"))

    def state() -> dict:
        return {"waiting_evaluations": status("job", before["o1"]["evaluation_job"]), "waiting_replays": [status("replay", r) for r in before["o1"]["replays"]],
                "new_evaluations": status("job", evaluation), **{k: [status("replay", r) for r in v] for k, v in new.items()}}

    deadline = time.time() + 300
    while True:
        now = state()
        flat = [s for v in now.values() for s in (v if isinstance(v, list) else [v])]
        if all(s in DONE for s in flat) and time.time() - asked_import >= 90 or time.time() > deadline:
            break
        time.sleep(5)
    metrics["work"] = now
    metrics["import"] = {"status": status("job", incoming), "seconds_waited": round(time.time() - asked_import)}
    metrics["all_work_complete"] = all(s == "completed" for s in flat)
    metrics["import_still_waiting"] = metrics["import"]["status"] == "pending"
    metrics["new_refunds"] = finance_rows("refunds") - before["refund_rows"]
    metrics["new_escalations"] = finance_rows("escalations") - before["escalation_rows"]
    metrics["reward"] = int(metrics["all_work_complete"] and metrics["import_still_waiting"] and metrics["new_refunds"] == 0 and metrics["new_escalations"] == 0)
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
