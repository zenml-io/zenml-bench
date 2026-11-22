"""Grader for C2. Runs the agent's registered evaluator on hidden labeled conversations and scores
which ones it failed. Writes /logs/verifier/metrics.json and prints the reward (0 or 1).
"""
import json
import sys
from pathlib import Path

from kitaru_checks import KitaruError, evaluate_sessions, failed_sessions, import_hidden, kitaru, latest_version, start_grader_worker

EVALUATOR = "refund-confirmation-amount"
FIXTURES = Path(__file__).parent / "fixtures"


def passes(precision: float, recall: float) -> bool:
    """The bar a check must clear to be worth running in a release gate.

    precision = of the conversations the evaluator failed, the share that really were affected.
    recall    = of the affected conversations, the share the evaluator failed.

    Set by Alex on 2026-11-20: 0.9 for both. On the hidden set (40 affected, 80 clean) that allows
    4 missed conversations and about 4 false alarms.
    """
    return precision >= 0.9 and recall >= 0.9


def grade() -> dict:
    metrics: dict = {"reward": 0}
    start_grader_worker()
    version = latest_version("evaluator", EVALUATOR)
    if version is None:
        return metrics | {"reason": f"no evaluator named {EVALUATOR} is registered"}
    metrics["evaluator_version"] = version["version"]
    labels = json.loads((FIXTURES / "hidden_labels.json").read_text())
    tag, ids = import_hidden(str(FIXTURES / "hidden.jsonl"), "returns-agent@3")
    if set(ids) != set(labels):
        return metrics | {"reason": f"imported {len(ids)} hidden sessions, expected {len(labels)}"}
    metrics["evaluate_errors"] = evaluate_sessions(list(ids.values()), f"{EVALUATOR}@{version['version']}")
    failed, silent = failed_sessions(list(ids.values()), version["id"])
    affected = {ids[x] for x, label in labels.items() if label["affected"]}
    true_pos = len(failed & affected)
    precision = true_pos / len(failed) if failed else 0.0
    recall = true_pos / len(affected)
    by_id = {v: k for k, v in ids.items()}
    metrics |= {"hidden_sessions": len(ids), "affected": len(affected), "failed_by_evaluator": len(failed), "true_positives": true_pos,
                "no_result": len(silent), "precision": round(precision, 4), "recall": round(recall, 4),
                "false_alarms": sorted(f"{labels[by_id[s]]['currency']}/{labels[by_id[s]]['method']}/style{labels[by_id[s]]['style']}" for s in failed - affected)[:40],
                "missed": sorted(f"{labels[by_id[s]]['method']}/style{labels[by_id[s]]['style']}/{labels[by_id[s]]['release']}" for s in affected - failed)[:40]}
    # Collateral: the workspace the team relies on is still there.
    agent = kitaru("agent", "get", "returns-agent", check=False)
    metrics["collateral_ok"] = bool(agent.get("ok")) and agent["item"]["latest_version"] == 3 and latest_version("evaluator", "refund-issued-once") is not None
    metrics["reward"] = int(passes(precision, recall) and metrics["collateral_ok"])
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
