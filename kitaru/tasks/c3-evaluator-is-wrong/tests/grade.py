"""Grader for C3. Runs the latest registered version of `polite-closing` on hidden labeled
conversations: curt replies must fail; polite replies and idle timeouts must pass. A new version must
have been registered. Writes /logs/verifier/metrics.json and prints the reward.
"""
import json
import sys
from collections import Counter
from pathlib import Path

from kitaru_checks import KitaruError, grade_evaluator_on_hidden, kitaru, latest_version

FIXTURES = Path(__file__).parent / "fixtures"


def passes(precision: float, recall: float) -> bool:
    """Same bar as C2 (Alex, 2026-11-20): of the conversations failed, 90% really curt; of the curt ones, 90% failed."""
    return precision >= 0.9 and recall >= 0.9


def describe(label: dict) -> str:
    return "idle timeout" if label["idle"] else f"curt variant {label['variant']}" if label["should_fail"] else "polite"


def grade() -> dict:
    labels = json.loads((FIXTURES / "hidden_labels.json").read_text())
    metrics = grade_evaluator_on_hidden("polite-closing", str(FIXTURES / "hidden.jsonl"), {x: v["should_fail"] for x, v in labels.items()}, "returns-agent@3", min_version=2)
    if "precision" not in metrics:
        return metrics | {"reward": 0}
    metrics["false_alarms"] = dict(Counter(describe(labels[x]) for x in metrics.pop("false_alarm_ids")))
    metrics["missed"] = dict(Counter(describe(labels[x]) for x in metrics.pop("missed_ids")))
    agent = kitaru("agent", "get", "returns-agent", check=False)
    metrics["collateral_ok"] = bool(agent.get("ok")) and agent["item"]["latest_version"] == 3 and latest_version("evaluator", "refund-issued-once") is not None
    metrics["reward"] = int(passes(metrics["precision"], metrics["recall"]) and metrics["collateral_ok"])
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
