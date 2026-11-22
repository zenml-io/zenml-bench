"""Grader for D8h. Reads the newest investigation named `week-30-triage`: it must link exactly the conversations of the last week that
`polite-closing` or `refund-issued-once@2` fails (an idle timeout, a curt reply, a refund issued twice), with the verdict
`problematic` on the curt replies and double refunds and `acceptable` on the idle timeouts. Runs none of the agent's code."""
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

NAME, WEEK_START = "week-30-triage", "2026-07-24"


def grade(truth: dict) -> dict:
    per = truth["per_session"]
    want = {x: "problematic" if v["curt"] or v["double_refund"] else "acceptable" for x, v in per.items() if v["started_at"] >= WEEK_START and (v["idle"] or v["curt"] or v["double_refund"])}
    external = {v: k for k, v in sessions_by_external_id().items()}
    named = [i for i in list_all("investigation", "list") if i["name"] == NAME]
    if not named:
        return {"reward": 0, "reason": f"no investigation named {NAME}"}
    chosen = max(named, key=lambda i: i["created"])
    agent_id = kitaru("agent", "get", "returns-agent")["item"]["id"]
    linked = {external.get(s["session_id"]): s["verdict"] for s in list_all("investigation", "session", "list", chosen["id"])}
    def kind(x: str) -> str:
        facts = per.get(x) or {}
        return next((k for k in ("curt", "double_refund", "idle", "wrong_amount", "late_refund") if facts.get(k)), "nothing planted" if facts else "not a history session")
    wrong_verdicts = {x: {"given": linked[x], "expected": want[x], "kind": kind(x)} for x in want if x in linked and linked[x] != want[x]}
    checks = {"right_agent": chosen["agent_id"] == agent_id, "links_exactly_the_failures": set(linked) == set(want), "verdicts_right": not wrong_verdicts}
    return {"investigations_with_name": len(named), "should_link": len(want), "linked": len(linked), "missing": sorted(kind(x) for x in set(want) - set(linked)),
            "should_not_be_linked": sorted(kind(x) for x in set(linked) - set(want)), "wrong_verdicts": list(wrong_verdicts.values()), **checks, "reward": int(all(checks.values()))}


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
