"""Grader for D8. Reads the newest investigation named `week-30-review`: three to six linked conversations from the last
week, each one a planted mistake (wrong amount stated, refund outside the window, refund issued twice, curt reply), at
least two kinds, each with the verdict `problematic`. Runs none of the agent's code."""
import json
import subprocess
import sys
from pathlib import Path

from kitaru_checks import KitaruError, kitaru, lock_grader_files, list_all, sessions_by_external_id


def workspace_intact(truth: dict) -> str | None:
    """None when the history and the agent's releases are as the task started; otherwise what changed."""
    ids = sessions_by_external_id()
    if set(ids) != set(truth["per_session"]):
        return f"the workspace holds {len(ids)} history sessions, expected {len(truth['per_session'])}"
    agent = kitaru("agent", "get", "returns-agent", check=False)
    if not agent.get("ok") or agent["item"]["latest_version"] != 3:
        return "the returns agent's releases were changed"
    return None

NAME, WEEK_START, KINDS = "week-30-review", "2026-07-24", ("wrong_amount", "late_refund", "double_refund", "curt")


def grade(truth: dict) -> dict:
    per = truth["per_session"]
    external = {v: k for k, v in sessions_by_external_id().items()}
    named = [i for i in list_all("investigation", "list") if i["name"] == NAME]
    if not named:
        return {"reward": 0, "reason": f"no investigation named {NAME}"}
    chosen = max(named, key=lambda i: i["created"])
    agent_id = kitaru("agent", "get", "returns-agent")["item"]["id"]
    linked = list_all("investigation", "session", "list", chosen["id"])
    rows = [{"session": external.get(s["session_id"]), "verdict": s["verdict"]} for s in linked]
    for row in rows:
        facts = per.get(row["session"]) or {}
        row |= {"in_week": bool(facts) and facts["started_at"] >= WEEK_START, "kinds": [k for k in KINDS if facts.get(k)], "idle": bool(facts.get("idle"))}
    kinds = {k for row in rows for k in row["kinds"]}
    checks = {"right_agent": chosen["agent_id"] == agent_id, "three_to_six": 3 <= len(rows) <= 6, "all_in_week": all(r["in_week"] for r in rows),
              "all_are_mistakes": all(r["kinds"] for r in rows), "two_kinds": len(kinds) >= 2, "all_problematic": all(r["verdict"] == "problematic" for r in rows)}
    return {"investigations_with_name": len(named), "linked": rows, "kinds": sorted(kinds), **checks, "reward": int(all(checks.values()))}


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
