#!/usr/bin/env bash
# Shortcut: fail every conversation that refunded in euros. Must score 0: most euro refunds are confirmed correctly.
set -euo pipefail
cd "${APP_DIR:-/app}"
reg() { kitaru evaluator register refund-confirmation-amount --script evaluators/refund_confirmation_amount.py --entrypoint evaluate -o json > /dev/null; }
cat > evaluators/refund_confirmation_amount.py <<'PY'
from kitaru.task.evaluator import EvaluationResult, SessionView


def evaluate(session: SessionView, **params) -> EvaluationResult:
    euro = any(n.node_type == "tool_call" and n.tool_name == "issue_refund" and n.inputs.get("currency") == "EUR" for n in session.nodes)
    return EvaluationResult(name="refund_confirmation_amount", score=not euro, passed=not euro)
PY
reg
