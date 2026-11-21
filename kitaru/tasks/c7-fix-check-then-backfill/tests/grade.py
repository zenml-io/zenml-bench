"""Grader for C7 (C3 and C4 in one). First reads what Kitaru stored: the latest version of `polite-closing` must cover every
conversation of release 1.4.1, almost nothing older, fail the curt ones there and pass the rest, and all versions together must
not have produced more than 1400 results. Then runs the latest version on hidden labeled conversations, as C3 does."""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from kitaru_checks import KitaruError, all_evaluations, grade_evaluator_on_hidden, kitaru, latest_version, lock_grader_files, sessions_by_external_id

FIXTURES = Path(__file__).parent / "fixtures"
EVALUATOR, RELEASE, OUTSIDE_ALLOWED, MAX_RESULTS = "polite-closing", "1.4.1", 30, 1400


def bar(precision: float, recall: float) -> bool:
    return precision >= 0.9 and recall >= 0.9


def stored(truth: dict) -> dict:
    """What the agent left in Kitaru, read before the grader evaluates anything itself."""
    ids = sessions_by_external_id()
    if set(ids) != set(truth):
        return {"stored_ok": False, "reason": f"the workspace holds {len(ids)} history sessions, expected {len(truth)}"}
    latest = latest_version("evaluator", EVALUATOR)
    if latest is None or latest["version"] < 2:
        return {"stored_ok": False, "reason": f"{EVALUATOR} has no new version"}
    rows = [e for e in all_evaluations() if e.get("evaluator_name") == EVALUATOR]
    mine = [e for e in rows if e.get("evaluator_version") == latest["version"]]
    in_release = {ids[x] for x, t in truth.items() if t["release"] == RELEASE}
    curt = {ids[x] for x, t in truth.items() if t["release"] == RELEASE and t["curt"]}
    covered = {e["session_id"] for e in mine}
    failed = {e["session_id"] for e in mine if e.get("passed") is False} & in_release
    hits = len(failed & curt)
    m = {"latest_version": latest["version"], "in_release": len(in_release), "covered": len(covered & in_release), "outside_release_evaluated": len(covered - in_release),
         "results_all_versions": len(rows), "results_by_version": dict(Counter(str(e.get("evaluator_version")) for e in rows)), "curt_in_release": len(curt), "failed_in_release": len(failed),
         "release_precision": round(hits / len(failed), 4) if failed else 0.0, "release_recall": round(hits / len(curt), 4)}
    m["stored_ok"] = in_release <= covered and m["outside_release_evaluated"] <= OUTSIDE_ALLOWED and len(rows) <= MAX_RESULTS and bar(m["release_precision"], m["release_recall"])
    return m


def describe(label: dict) -> str:
    return "idle timeout" if label["idle"] else f"curt variant {label['variant']}" if label["should_fail"] else "polite"


def grade() -> dict:
    lock_grader_files()
    subprocess.run(["/opt/kitaru-bench/start.sh", "--no-worker"], capture_output=True)
    metrics = stored(json.loads((FIXTURES / "ground_truth.json").read_text())["per_session"])
    labels = json.loads((FIXTURES / "hidden_labels.json").read_text())
    hidden = grade_evaluator_on_hidden(EVALUATOR, str(FIXTURES / "hidden.jsonl"), {x: v["should_fail"] for x, v in labels.items()}, "returns-agent@3", min_version=2)
    if "precision" not in hidden:
        return metrics | hidden | {"reward": 0}
    hidden["false_alarms"] = dict(Counter(describe(labels[x]) for x in hidden.pop("false_alarm_ids")))
    hidden["missed"] = dict(Counter(describe(labels[x]) for x in hidden.pop("missed_ids")))
    agent = kitaru("agent", "get", "returns-agent", check=False)
    metrics |= hidden
    metrics["collateral_ok"] = bool(agent.get("ok")) and agent["item"]["latest_version"] == 3 and latest_version("evaluator", "refund-issued-once") is not None
    metrics["reward"] = int(metrics["stored_ok"] and bar(hidden["precision"], hidden["recall"]) and metrics["collateral_ok"])
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
