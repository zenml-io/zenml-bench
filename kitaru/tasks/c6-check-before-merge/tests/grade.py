"""Grader for C6. Creates four cohorts from hidden conversations, runs the agent's `bin/check.sh` on
each, and checks two things per cohort: the exit status, and that Kitaru holds results from every
evaluator in checks.txt for every conversation in the cohort. Writes metrics.json, prints the reward.

The script is the agent's code and runs during grading, as user `agent`, after the grader's files
have been locked and with the grader's own worker running.
"""
import json
import subprocess
import sys
import uuid
from pathlib import Path

from kitaru_checks import KitaruError, all_evaluations, import_hidden, kitaru, start_grader_worker

FIXTURES = Path(__file__).parent / "fixtures"
BAR = 0.90
CHECKS = ["refund-issued-once@2"]  # what checks.txt lists in the image


def grade() -> dict:
    start_grader_worker()
    script = Path("/app/bin/check.sh")
    if not script.is_file():
        return {"reward": 0, "reason": "there is no /app/bin/check.sh"}
    if [l.strip() for l in Path("/app/checks.txt").read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")] != CHECKS:
        return {"reward": 0, "reason": "checks.txt was changed"}
    labels = json.loads((FIXTURES / "hidden_labels.json").read_text())
    _, ids = import_hidden(str(FIXTURES / "hidden.jsonl"), "returns-agent@3")
    if set(ids) != set(labels):
        return {"reward": 0, "reason": f"imported {len(ids)} hidden sessions, expected {len(labels)}"}
    version_ids = {c: kitaru("evaluator", "version", "get", c)["item"]["id"] for c in CHECKS}
    cohorts, all_ok = {}, True
    for group in sorted({v["group"] for v in labels.values()}):
        members = [x for x, v in labels.items() if v["group"] == group]
        name = f"release-candidate-{uuid.uuid4().hex[:8]}"  # says nothing about which group it is
        listing = Path(f"/tmp/{name}.txt")
        listing.write_text("".join(ids[x] + "\n" for x in members))
        kitaru("cohort", "create", name, "--agent", "returns-agent", "--sessions-file", str(listing))
        expected = 0 if 1 - sum(labels[x]["double_refund"] for x in members) / len(members) >= BAR else 1
        try:
            status = subprocess.run(["runuser", "-u", "agent", "--", "env", "HOME=/home/agent", "bash", str(script), name], cwd="/app",
                                    capture_output=True, text=True, timeout=600).returncode
        except subprocess.TimeoutExpired:
            status = "timeout"
        cohorts[group] = {"conversations": len(members), "expected_exit": expected, "exit": status}
        all_ok &= status == expected
    rows = all_evaluations()
    for group, info in cohorts.items():
        members = {ids[x] for x, v in labels.items() if v["group"] == group}
        covered = min(len(members & {r["session_id"] for r in rows if r.get("evaluator_version_id") == vid}) for vid in version_ids.values())
        info["with_results"] = covered
        all_ok &= covered == len(members)
    missing = subprocess.run(["runuser", "-u", "agent", "--", "env", "HOME=/home/agent", "bash", str(script), f"no-such-cohort-{uuid.uuid4().hex[:6]}"],
                             cwd="/app", capture_output=True, text=True, timeout=120).returncode
    agent = kitaru("agent", "get", "returns-agent", check=False)
    collateral = bool(agent.get("ok")) and agent["item"]["latest_version"] == 3
    return {"cohorts": cohorts, "exit_for_missing_cohort": missing, "collateral_ok": collateral, "reward": int(all_ok and missing == 2 and collateral)}


if __name__ == "__main__":
    try:
        result = grade()
    except KitaruError as e:
        result = {"reward": 0, "reason": f"grader could not finish: {e}"}
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/metrics.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1), file=sys.stderr)
    print(result["reward"])
