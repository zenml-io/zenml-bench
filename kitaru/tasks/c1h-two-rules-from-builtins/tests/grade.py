"""Grader for C1h. Reads the evaluations Kitaru stored for the week of 9 to 15 July. For each of the two rules (at most three
`lookup_order` calls; every model call served by exactly `gpt-5.4-mini`) some built-in evaluator must have stated the right
`passed` for every conversation of the week. Runs none of the agent's code."""
import json
import subprocess
import sys
from pathlib import Path

from kitaru_checks import KitaruError, all_evaluations, kitaru, lock_grader_files, sessions_by_external_id

START, END, MAX_CALLS, OUTSIDE_ALLOWED = "2026-07-09T00:00:00", "2026-07-16T00:00:00", 3, 50


def grade() -> dict:
    lock_grader_files()
    subprocess.run(["/opt/kitaru-bench/start.sh", "--no-worker"], capture_output=True)
    truth = json.loads((Path(__file__).parent / "fixtures" / "ground_truth.json").read_text())
    per, swapped = truth["per_session"], set(truth["planted"]["model_swap"])
    ids = sessions_by_external_id()
    if set(ids) != set(per):
        return {"reward": 0, "reason": f"the workspace holds {len(ids)} history sessions, expected {len(per)}"}
    in_week = {ids[x] for x, t in per.items() if START <= t["started_at"] < END}
    rules = {"lookups": {ids[x]: t["lookups"] <= MAX_CALLS for x, t in per.items()}, "served_model": {ids[x]: x not in swapped for x in per}}
    builtin = [e for e in all_evaluations() if (e.get("evaluator_name") or "").startswith("kitaru/")]
    verdicts: dict[str, dict[str, bool]] = {}  # per evaluator, per session: the most recent result that states pass or fail
    for e in builtin:
        if e.get("passed") is not None:
            verdicts.setdefault(e["evaluator_name"], {})[e["session_id"]] = e["passed"]
    metrics: dict = {"in_week": len(in_week), "builtin_evaluators_used": sorted({e["evaluator_name"] for e in builtin}),
                     "results_with_no_verdict": sum(e.get("passed") is None for e in builtin if e["session_id"] in in_week)}
    chosen = {}
    for rule, should_pass in rules.items():
        scores = {name: sum(1 for s in in_week if stated.get(s) is should_pass[s]) for name, stated in verdicts.items() if name not in chosen.values()}
        best = max(scores, key=scores.get, default=None)
        chosen[rule] = best
        metrics[rule] = {"evaluator": best, "correct": scores.get(best, 0), "rule_breakers_in_week": sum(1 for s in in_week if not should_pass[s]),
                         "stated": len(in_week & set(verdicts.get(best, {})))}
    outside = {e["session_id"] for e in builtin} - in_week
    agent = kitaru("agent", "get", "returns-agent", check=False)
    metrics |= {"outside_week_evaluated": len(outside), "collateral_ok": bool(agent.get("ok")) and agent["item"]["latest_version"] == 3}
    metrics["reward"] = int(all(metrics[rule]["correct"] == len(in_week) for rule in rules) and len(outside) <= OUTSIDE_ALLOWED and metrics["collateral_ok"])
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
