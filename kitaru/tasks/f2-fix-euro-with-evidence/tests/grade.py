"""Grader for F2 and F3. Checks, in this order: releases 1.6.0 and 1.6.1 and the data are untouched; the newest agent version is
1.6.2 and runs from its own directory; the finance service received no call from the agent's work; a completed experiment run
of the newest version exists over at least 20 conversations, with a higher pass rate in its results than in its baselines.
Then it records hidden refund requests with release 1.6.1 (those runs are live, and are the grader's own) and replays them
against the newest version on its own worker: every refund must be right, yen included."""
import json
import sys
from pathlib import Path

from kitaru_checks import (KitaruError, finance_rows, kitaru, latest_version, list_all, record_requests, replay_sessions, repo_changed,
                           start_grader_worker, verdict)

FIXTURES = Path(__file__).parent / "fixtures"
BEFORE, AGENT, EVALUATOR = "/etc/kitaru-bench/helpdesk.json", "helpdesk-agent", "refund-amount"
MIN_COHORT = 20
NEED_EXPERIMENT = True  # F3 asks for the fix only


def evidence(newest_id: str) -> dict:
    """The best experiment run the agent left: completed, against the newest version, over enough conversations."""
    replays: dict[str, list[dict]] = {}
    for r in list_all("replay", "list"):
        if r.get("experiment_run_id"):
            replays.setdefault(r["experiment_run_id"], []).append(r)
    evaluations: dict[str, list[dict]] = {}
    for e in list_all("evaluation", "list"):
        if e.get("evaluator_name") == EVALUATOR and e.get("passed") is not None:
            evaluations.setdefault(e["session_id"], []).append(e)
    newest = lambda session: max(evaluations[session], key=lambda e: e["created"])["passed"] if session in evaluations else None
    best: dict = {"runs_seen": len(replays), "ok": False}
    for run_id, rows in replays.items():
        run = kitaru("experiment", "run", "get", run_id, check=False).get("item") or {}
        run = run.get("run", run)
        pairs = [(newest(r["baseline_session_id"]), newest(r["result_session_id"]) if r.get("result_session_id") else None) for r in rows]
        judged = [p for p in pairs if p[0] is not None and p[1] is not None]
        summary = {"status": run.get("status"), "against_newest_version": run.get("agent_version_id") == newest_id, "conversations": len(rows),
                   "judged_on_both_sides": len(judged), "baseline_pass_rate": round(sum(p[0] for p in judged) / len(judged), 4) if judged else None,
                   "result_pass_rate": round(sum(p[1] for p in judged) / len(judged), 4) if judged else None}
        summary["ok"] = (summary["status"] == "completed" and summary["against_newest_version"] and len(rows) >= MIN_COHORT and len(judged) == len(rows)
                         and summary["result_pass_rate"] > summary["baseline_pass_rate"])
        if summary["ok"] or not best.get("status"):
            best = {"runs_seen": len(replays), **summary}
        if summary["ok"]:
            break
    return best


def grade() -> dict:
    before = json.loads(Path(BEFORE).read_text())
    agent = kitaru("agent", "get", AGENT, check=False)
    if not agent.get("ok") or agent["item"]["id"] != before["agent_id"]:
        return {"reward": 0, "reason": f"{AGENT} is not the agent that was registered"}
    versions = sorted(list_all("agent", "version", "list", AGENT), key=lambda v: v["version"])
    newest = versions[-1]
    spec = newest.get("run_spec") or {}
    metrics: dict = {"old_releases_untouched": not repo_changed(before["head"], "releases/1.6.0", "releases/1.6.1", "data"),
                     "newest_version": {"version": newest["version"], "display_version": newest.get("display_version"), "working_dir": spec.get("working_dir")},
                     "new_refunds": finance_rows("refunds") - before["refund_rows"], "new_escalations": finance_rows("escalations") - before["escalation_rows"]}
    metrics["version_ok"] = newest["version"] >= 3 and newest.get("display_version") == "1.6.2" and (spec.get("working_dir") or "").rstrip("/") == "/app/releases/1.6.2" and bool(spec.get("command"))
    metrics["experiment"] = evidence(newest["id"])
    if not (metrics["old_releases_untouched"] and metrics["version_ok"]):
        return metrics | {"reward": 0, "reason": "the old releases were changed, or the newest version is not 1.6.2 run from /app/releases/1.6.2"}

    start_grader_worker()
    mine = kitaru("evaluator", "register", f"grader-refund-amount", "--script", str(FIXTURES / "refund_amount.py"), "--entrypoint", "evaluate", check=False)
    grader_evaluator = latest_version("evaluator", "grader-refund-amount")
    hidden = json.loads((FIXTURES / "hidden_requests.json").read_text())
    refunds_before = finance_rows("refunds")
    sessions = record_requests(hidden, "/app/releases/1.6.1", before["agent_id"], before["versions"]["1.6.1"])
    recorded = finance_rows("refunds") - refunds_before
    replays = replay_sessions([sessions[r["id"]] for r in hidden if r["id"] in sessions], f"{AGENT}@{newest['version']}", f"grader-refund-amount@{grader_evaluator['version']}")
    by_currency: dict[str, list[bool]] = {}
    for r in hidden:
        replay = replays.get(sessions.get(r["id"], ""), {})
        right = replay.get("status") == "completed" and verdict(replay["result_session_id"], grader_evaluator["id"]) is True
        by_currency.setdefault(r["currency"], []).append(right)
    metrics["hidden"] = {"requests": len(hidden), "recorded": len(sessions), "refunds_made_while_recording": recorded, "refunds_made_by_grader_replays": finance_rows("refunds") - refunds_before - recorded,
                         "right_by_currency": {c: f"{sum(v)}/{len(v)}" for c, v in by_currency.items()}, "statuses": sorted({r.get("status") for r in replays.values()})}
    metrics["hidden_ok"] = len(sessions) == len(hidden) and all(all(v) for v in by_currency.values())
    metrics["reward"] = int((metrics["experiment"]["ok"] or not NEED_EXPERIMENT) and metrics["hidden_ok"] and metrics["new_refunds"] == 0 and metrics["new_escalations"] == 0)
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
