#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
reg() { if kitaru evaluator get matches-review -o json > /dev/null 2>&1; then kitaru evaluator version register matches-review --script evaluators/matches_review.py --entrypoint evaluate -o json > /dev/null; else kitaru evaluator register matches-review --script evaluators/matches_review.py --entrypoint evaluate -o json > /dev/null; fi; }
# write_check <python expression that is True when the conversation should FAIL; it may use `late`, `days`, `refunds`, `wrong_amount`, `session`>
write_check() { cat > evaluators/matches_review.py <<PY
import re
from decimal import Decimal, InvalidOperation

from kitaru.task.evaluator import EvaluationResult, SessionView

BEFORE = re.compile(r"[€\$£¥]\s?(\d[\d.,]*\d|\d)")
AFTER = re.compile(r"(\d[\d.,]*\d|\d)\s?€")


def stated_amounts(text: str) -> list[Decimal]:
    found = [m.replace(",", "") for m in BEFORE.findall(text)] + [m.replace(".", "").replace(",", ".") for m in AFTER.findall(text)]
    out = []
    for item in found:
        try:
            out.append(Decimal(item))
        except InvalidOperation:
            pass
    return out


def evaluate(session: SessionView, **params) -> EvaluationResult:
    tools = [n for n in session.nodes if n.node_type == "tool_call"]
    refunds = [Decimal(str(n.inputs["amount"])) for n in tools if n.tool_name == "issue_refund"]
    looked_up = [n.outputs for n in tools if n.tool_name == "lookup_order" and isinstance(n.outputs, dict) and "days_since_delivery" in n.outputs]
    days = looked_up[-1]["days_since_delivery"] if looked_up else 0
    late = bool(refunds) and days > 30
    outputs = session.session.outputs
    stated = stated_amounts(outputs.get("reply", "") if isinstance(outputs, dict) else "")
    wrong_amount = any(r * 100 in stated and r not in stated for r in refunds)
    bad = bool($1)
    return EvaluationResult(name="matches_review", score=not bad, passed=not bad, explanation=f"days={days}, refunds={[str(r) for r in refunds]}, wrong_amount={wrong_amount}")
PY
}
# Shortcut: one of the reviewers' two rules. Must score 0: the wrong-amount conversations pass.
write_check 'late'
reg
