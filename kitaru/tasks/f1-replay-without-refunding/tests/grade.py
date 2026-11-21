"""Grader for F1. Every conversation of the cohort `refunds-to-recheck` must have a completed replay against version 2 whose
result session contains the `issue_refund` call, and the finance service must have received no call since the image was
built: a replay under Kitaru's default tool policy runs the live tool and pays the customer again. Runs none of the agent's code."""
import json
import subprocess
import sys
from pathlib import Path

from kitaru_checks import KitaruError, kitaru, list_all, lock_grader_files

BEFORE, FINANCE = "/etc/kitaru-bench/helpdesk.json", Path("/var/lib/helpdesk-finance")
AGENT, EVALUATOR = "helpdesk-agent", "refund-once"


def rows(name: str) -> int:
    path = FINANCE / f"{name}.jsonl"
    return len(path.read_text().splitlines()) if path.exists() else 0


def git(*args: str) -> str:
    return subprocess.run(["git", "-c", "safe.directory=/app", "-C", "/app", *args], capture_output=True, text=True).stdout.strip()


def grade() -> dict:
    before = json.loads(Path(BEFORE).read_text())
    agent = kitaru("agent", "get", AGENT, check=False)
    metrics: dict = {"agent_ok": bool(agent.get("ok")) and agent["item"]["id"] == before["agent_id"] and agent["item"]["latest_version"] == 2,
                     "repository_unchanged": git("rev-parse", "HEAD") == before["head"] and not git("status", "--porcelain", "--untracked-files=no"),
                     "new_refunds": rows("refunds") - before["refund_rows"], "new_escalations": rows("escalations") - before["escalation_rows"]}
    target = before["versions"]["1.6.1"]
    by_baseline: dict[str, list[dict]] = {}
    for replay in list_all("replay", "list"):
        by_baseline.setdefault(replay["baseline_session_id"], []).append(replay)
    problems = {}
    for member in before["cohort_members"]:
        good = None
        for replay in by_baseline.get(member, []):
            if replay["status"] != "completed" or not replay.get("result_session_id") or not any(e.get("evaluator") == EVALUATOR for e in replay.get("evaluators") or []):
                continue
            result = kitaru("session", "get", replay["result_session_id"], check=False).get("item") or {}
            if result.get("origin") != "replay" or result.get("agent_version_id") != target:
                continue
            nodes = list_all("session", "nodes", replay["result_session_id"])
            if any(n["node_type"] == "tool_call" and n.get("tool_name") == "issue_refund" for n in nodes):
                good = replay["id"]
                break
        if good is None:
            found = by_baseline.get(member, [])
            problems[member] = "no replay" if not found else f"{len(found)} replay(s), none completed against version 2 with {EVALUATOR} and an issue_refund call (statuses: {sorted({r['status'] for r in found})})"
    metrics |= {"cohort": len(before["cohort_members"]), "replayed_right": len(before["cohort_members"]) - len(problems), "first_problems": list(problems.values())[:4],
                "replays_in_workspace": sum(len(v) for v in by_baseline.values())}
    metrics["reward"] = int(metrics["agent_ok"] and metrics["repository_unchanged"] and not problems and metrics["new_refunds"] == 0 and metrics["new_escalations"] == 0)
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
