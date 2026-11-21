"""Grader for I2. Compares the sessions under `support-assistant` with the export the agent was given, then runs the
agent's bin/import_tickets.sh on an export it never saw and compares again: one session per ticket, each holding the ticket's
turns in order, none for a trace without a ticket."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from kitaru_checks import KitaruError, kitaru, list_all, run_agent_script, start_grader_worker, ticket_problems

FIXTURES = Path(__file__).parent / "fixtures"
AGENT, SCRIPT = "support-assistant", "/app/bin/import_tickets.sh"


def compare(want: dict, sessions: list[dict], version_id: str) -> dict:
    problems = ticket_problems(sessions, want["tickets"], want["project"], {release: version_id for release in {t["release"] for t in want["tickets"].values()}})
    return {"tickets": len(want["tickets"]), "right": len(want["tickets"]) - len(problems), "first_problems": dict(sorted(problems.items())[:6])}


def grade() -> dict:
    seen, hidden = json.loads((FIXTURES / "expected.json").read_text()), json.loads((FIXTURES / "hidden_expected.json").read_text())
    agent = kitaru("agent", "get", AGENT)["item"]
    version_id = kitaru("agent", "version", "get", f"{AGENT}@1")["item"]["id"]
    before = list_all("session", "list", "--agent", AGENT)
    wanted = {f"{seen['project']}:{t}" for t in seen["tickets"]}
    metrics: dict = {"agent_ok": agent["latest_version"] == 1, "given_export": compare(seen, before, version_id), "unexpected_sessions_before": sum(s.get("external_id") not in wanted for s in before)}
    if not os.path.isfile(SCRIPT) or os.path.islink(SCRIPT):
        return metrics | {"reward": 0, "reason": f"{SCRIPT} does not exist"}
    start_grader_worker()
    folder = tempfile.mkdtemp(prefix="exports-")  # the file is the script's input, so the agent's user may read it; the answer key stays locked
    shutil.copy(FIXTURES / "hidden_export.jsonl", f"{folder}/langfuse-observations-2026-08-02.jsonl")
    os.chmod(folder, 0o755); os.chmod(f"{folder}/langfuse-observations-2026-08-02.jsonl", 0o644)
    metrics["script_run"] = run_agent_script(SCRIPT, f"{folder}/langfuse-observations-2026-08-02.jsonl")
    after = list_all("session", "list", "--agent", AGENT)
    wanted |= {f"{hidden['project']}:{t}" for t in hidden["tickets"]}
    metrics |= {"hidden_export": compare(hidden, after, version_id), "unexpected_sessions_after": sum(s.get("external_id") not in wanted for s in after),
                "given_export_after": compare(seen, after, version_id)["right"]}
    metrics["reward"] = int(metrics["agent_ok"] and metrics["script_run"]["exit_code"] == 0 and not metrics["unexpected_sessions_before"] and not metrics["unexpected_sessions_after"]
                            and all(metrics[k]["right"] == metrics[k]["tickets"] for k in ("given_export", "hidden_export")) and metrics["given_export_after"] == len(seen["tickets"]))
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
