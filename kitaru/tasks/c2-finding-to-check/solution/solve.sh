#!/usr/bin/env bash
# Reference: compare every amount the reply states with the amount the refund tool was called with.
set -euo pipefail
cd "${APP_DIR:-/app}"
cat > evaluators/refund_confirmation_amount.py <<'PY'
import re
from decimal import Decimal, InvalidOperation

from kitaru.task.evaluator import EvaluationResult, SessionView

# An amount as the shop writes it: a currency sign before the number, or a euro sign after it.
BEFORE = re.compile(r"[€$£¥]\s?(\d[\d.,]*\d|\d)")
AFTER = re.compile(r"(\d[\d.,]*\d|\d)\s?€")


def stated_amounts(text: str) -> list[Decimal]:
    """Every money amount in the reply. `€1,300.00` uses a comma for thousands; `1.300,00 €` uses a dot."""
    found = [m.replace(",", "") for m in BEFORE.findall(text)] + [m.replace(".", "").replace(",", ".") for m in AFTER.findall(text)]
    amounts = []
    for item in found:
        try:
            amounts.append(Decimal(item))
        except InvalidOperation:
            pass
    return amounts


def evaluate(session: SessionView, **params) -> EvaluationResult:
    refunds = [n for n in session.nodes if n.node_type == "tool_call" and n.tool_name == "issue_refund"]
    outputs = session.session.outputs
    reply = outputs.get("reply", "") if isinstance(outputs, dict) else str(outputs or "")
    stated = stated_amounts(reply)
    wrong = [str(r.inputs["amount"]) for r in refunds if Decimal(str(r.inputs["amount"])) * 100 in stated and Decimal(str(r.inputs["amount"])) not in stated]
    return EvaluationResult(name="refund_confirmation_amount", score=not wrong, passed=not wrong,
                            explanation=f"refunded {[str(r.inputs['amount']) for r in refunds]}, reply states {[str(a) for a in stated]}")
PY
kitaru evaluator register refund-confirmation-amount --script evaluators/refund_confirmation_amount.py --entrypoint evaluate \
  --description "Fails when the reply states 100 times the refunded amount." -o json > /dev/null
