"""Grader for I4h. Everything I4 checks, and then: the grader imports 500 strays and 1,200 good sessions (more than one page of any
listing) and runs the agent's bin/remove_strays.sh. What follows is I4's description.

Grader for I4. Checks that every ticket of the nightly files is in Kitaru once under the stable source identity, that the
sessions and the cohort that were right before the agent started are the same objects, and then runs the agent's nightly
script twice on the next night's file."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from kitaru_checks import KitaruError, kitaru, list_all, run_agent_script, start_grader_worker, ticket_problems

FIXTURES = Path(__file__).parent / "fixtures"
AGENT, COHORT, SCRIPT = "support-assistant", "reviewed-week-31", "/app/bin/nightly_import.sh"


def state(want: dict, last_day: int, before: dict) -> dict:
    """Compare the sessions under the agent with every ticket up to `last_day` (1-based)."""
    tickets = {t: w for t, w in want["tickets"].items() if w["day"] + 1 <= last_day}
    sessions = list_all("session", "list", "--agent", AGENT)
    problems = ticket_problems(sessions, tickets, want["project"])
    wanted = {f"{want['project']}:{t}" for t in tickets}
    ids = {s["external_id"]: s["id"] for s in sessions}
    return {"tickets": len(tickets), "right": len(tickets) - len(problems), "first_problems": dict(sorted(problems.items())[:6]), "sessions": len(sessions),
            "unexpected_sessions": sum(s.get("external_id") not in wanted for s in sessions),
            "originals_kept": sum(ids.get(external) == session for external, session in before["originals"].items()), "ids": sorted(s["id"] for s in sessions)}


def ok(s: dict, before: dict) -> bool:
    return s["right"] == s["tickets"] and not s["unexpected_sessions"] and s["originals_kept"] == len(before["originals"])


def grade_i4() -> dict:
    want = json.loads((FIXTURES / "expected.json").read_text())
    before = json.loads(Path("/etc/kitaru-bench/i4.json").read_text())
    agent = kitaru("agent", "get", AGENT, check=False)
    metrics: dict = {"agent_ok": bool(agent.get("ok")) and agent["item"]["id"] == before["agent_id"] and agent["item"]["latest_version"] == 1}
    if not metrics["agent_ok"]:
        return metrics | {"reward": 0, "reason": f"{AGENT} is not the agent that was registered, or has a new version"}
    cohort = kitaru("cohort", "get", COHORT, check=False)
    metrics["cohort_ok"] = (bool(cohort.get("ok")) and cohort["item"]["id"] == before["cohort_id"] and cohort["item"]["latest_version"] == 1
                            and sorted(s["id"] for s in list_all("session", "list", "--cohort", f"{COHORT}@1")) == before["cohort_members"])
    metrics["found"] = state(want, 7, before)
    found_ok = ok(metrics["found"], before)
    del metrics["found"]["ids"]
    if not os.path.isfile(SCRIPT) or os.path.islink(SCRIPT):
        return metrics | {"reward": 0, "reason": f"{SCRIPT} does not exist"}
    start_grader_worker()
    folder = tempfile.mkdtemp(prefix="nightly-")  # the file is the script's input, so the agent's user may read it; the answer key stays locked
    shutil.copy(FIXTURES / "next_night.jsonl", f"{folder}/support-2026-08-08.jsonl")
    os.chmod(folder, 0o755); os.chmod(f"{folder}/support-2026-08-08.jsonl", 0o644)
    runs = []
    for number in (1, 2):
        metrics[f"run_{number}"] = run_agent_script(SCRIPT, f"{folder}/support-2026-08-08.jsonl")
        runs.append(state(want, 8, before))
    metrics["after_first_run"], metrics["after_second_run"] = ({k: v for k, v in r.items() if k != "ids"} for r in runs)
    metrics["second_run_changed_nothing"] = runs[0]["ids"] == runs[1]["ids"]
    metrics["reward"] = int(found_ok and metrics["cohort_ok"] and metrics["run_1"]["exit_code"] == 0 and metrics["run_2"]["exit_code"] == 0
                            and ok(runs[0], before) and ok(runs[1], before) and metrics["second_run_changed_nothing"])
    return metrics


REMOVE, STRAYS, GOOD = "/app/bin/remove_strays.sh", 500, 1200


def load(path: str, identity: str) -> bool:
    run = kitaru("session", "import", path, "--importer", "kitaru/langfuse@latest", "--agent", f"{AGENT}@1", "--params", json.dumps({"source_instance": identity}),
                 "--media-type", "application/x-ndjson", "--wait", "--timeout", "800", "--request-timeout", "300", check=False)
    return bool(run.get("ok"))


def grade() -> dict:
    metrics = grade_i4()
    if "after_second_run" not in metrics:   # stopped early: no agent, or no nightly script
        return metrics
    earlier = metrics["reward"]
    metrics["reward"] = 0
    if not os.path.isfile(REMOVE) or os.path.islink(REMOVE):
        return metrics | {"reason": f"{REMOVE} does not exist"}
    from support_story import tickets, trace_rows, write
    found = tickets(4242, GOOD, "TK-7", days=30)
    folder = Path(tempfile.mkdtemp(prefix="scale-"))
    write(folder / "strays.jsonl", trace_rows(found[:STRAYS]))
    write(folder / "good.jsonl", trace_rows(found))
    start = list_all("session", "list", "--agent", AGENT)
    before = {s["id"] for s in start if (s.get("external_id") or "").startswith("tidewater-support:")}
    # strays first, so they are the oldest: a listing that reads one page of the newest sessions sees none of them
    loaded = load(str(folder / "strays.jsonl"), "support-2026-09-01") and load(str(folder / "good.jsonl"), "tidewater-support")
    held = list_all("session", "list", "--agent", AGENT)
    good = {s["id"] for s in held if (s.get("external_id") or "").startswith("tidewater-support:")}
    scale = {"loaded": loaded and len(held) - len(good) == len(start) - len(before) + STRAYS and len(good) == len(before) + GOOD, "sessions_before_script": len(held), "strays_before_script": len(held) - len(good)}
    scale["script_run"] = run_agent_script(REMOVE)
    after = {s["id"]: s.get("external_id") or "" for s in list_all("session", "list", "--agent", AGENT)}
    scale |= {"strays_left": sum(not e.startswith("tidewater-support:") for e in after.values()), "good_sessions_lost": len(good - set(after)), "sessions_after_script": len(after)}
    cohort = kitaru("cohort", "get", COHORT, check=False)
    scale["cohort_still_there"] = bool(cohort.get("ok")) and cohort["item"]["latest_version"] == 1
    metrics["at_scale"] = scale
    if not scale["loaded"]:
        raise KitaruError(f"the grader could not load its larger store: {scale}")
    metrics["reward"] = int(earlier == 1 and scale["script_run"]["exit_code"] == 0 and not scale["strays_left"] and not scale["good_sessions_lost"] and scale["cohort_still_there"])
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
