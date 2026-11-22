#!/usr/bin/env bash
# A different valid check, reached the way a real agent gets there: a first version that is too
# strict (it fails replies that state no amount), a corrected second version, and a run of the
# check over the recorded history before stopping. The grader must use the latest version.
set -euo pipefail
cd "${APP_DIR:-/app}"
write() {  # $1 = what to do when the reply states no amount: True (pass) or False (fail)
cat > evaluators/refund_confirmation_amount.py <<PY
import re
from decimal import Decimal

from kitaru.task.evaluator import EvaluationResult, SessionView

NUMBER = r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)"


def to_decimal(raw: str, german: bool) -> Decimal:
    return Decimal(raw.replace(".", "").replace(",", ".")) if german else Decimal(raw.replace(",", ""))


def evaluate(session: SessionView, **params) -> list[EvaluationResult]:
    reply = (session.session.outputs or {}).get("reply", "")
    stated = [to_decimal(m, False) for m in re.findall(r"[€\$£¥]\s?" + NUMBER, reply)] + [to_decimal(m, True) for m in re.findall(NUMBER + r"\s?€", reply)]
    results = []
    for node in session.nodes:
        if node.node_type == "tool_call" and node.tool_name == "issue_refund":
            refunded = Decimal(str(node.inputs["amount"]))
            ok = $1 if not stated else refunded in stated
            results.append(EvaluationResult(name=f"confirmation_matches_refund", score=ok, passed=ok, explanation=f"refunded {refunded}, stated {[str(s) for s in stated]}"))
    return results or [EvaluationResult(name="confirmation_matches_refund", score=True, passed=True, explanation="no refund")]
PY
}
write False
kitaru evaluator register refund-confirmation-amount --script evaluators/refund_confirmation_amount.py --entrypoint evaluate -o json > /dev/null
write True
kitaru evaluator version register refund-confirmation-amount --script evaluators/refund_confirmation_amount.py --entrypoint evaluate -o json > /dev/null
kitaru session evaluate --tag history --evaluator refund-confirmation-amount@2 --wait --timeout 1200 -o json > /tmp/backfill.json || true
kitaru cohort create scratch-euro-check --agent returns-agent --filter '{"field":"started_at","op":"gte","value":"2026-07-29T00:00:00Z"}' -o json > /dev/null || true
