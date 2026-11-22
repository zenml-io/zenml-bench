"""Grader for C5. Runs the latest registered version of `matches-review` on hidden conversations
judged by the reviewers' rules, and on the 40 reviewed conversations. Needs precision and recall of
0.9 on the hidden set and agreement of 0.9 on the reviewed one. Writes metrics.json, prints the reward.
"""
import json
import sys
from collections import Counter
from pathlib import Path

from kitaru_checks import KitaruError, evaluate_sessions, failed_sessions, grade_evaluator_on_hidden, kitaru, latest_version, sessions_by_external_id

FIXTURES = Path(__file__).parent / "fixtures"


def describe(label: dict) -> str:
    if label["late_refund"] or label["wrong_amount"]:
        return "+".join(k for k in ("late_refund", "wrong_amount") if label[k])
    return f"fine, {label['kind']}, day {label['days']}" if label["days"] else f"fine, {label['kind']}"


def grade() -> dict:
    labels = json.loads((FIXTURES / "hidden_labels.json").read_text())
    metrics = grade_evaluator_on_hidden("matches-review", str(FIXTURES / "hidden.jsonl"), {x: v["should_fail"] for x, v in labels.items()}, "returns-agent@3")
    if "precision" not in metrics:
        return metrics | {"reward": 0}
    metrics["false_alarms"] = dict(Counter(describe(labels[x]) for x in metrics.pop("false_alarm_ids")))
    metrics["missed"] = dict(Counter(describe(labels[x]) for x in metrics.pop("missed_ids")))
    # The 40 the reviewers read: the evaluator must agree with the verdicts stored in Kitaru.
    reviewed = json.loads((FIXTURES / "ground_truth.json").read_text())["reviewed"]
    ids = sessions_by_external_id()
    version = latest_version("evaluator", "matches-review")
    evaluate_sessions([ids[x] for x in reviewed], f"matches-review@{version['version']}")
    failed, silent = failed_sessions([ids[x] for x in reviewed], version["id"])
    agree = sum(1 for x, passed in reviewed.items() if (ids[x] not in failed) == passed and ids[x] not in silent)
    metrics["reviewed_agreement"] = round(agree / len(reviewed), 4)
    agent = kitaru("agent", "get", "returns-agent", check=False)
    metrics["collateral_ok"] = bool(agent.get("ok")) and agent["item"]["latest_version"] == 3
    metrics["reward"] = int(metrics["precision"] >= 0.9 and metrics["recall"] >= 0.9 and metrics["reviewed_agreement"] >= 0.9 and metrics["collateral_ok"])
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
