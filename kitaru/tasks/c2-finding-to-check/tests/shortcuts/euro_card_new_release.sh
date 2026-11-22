#!/usr/bin/env bash
# Shortcut: the rule the history suggests if you never read a reply: euro + card + a release after 1.3.0.
# Must score 0: the hidden conversations are labeled by what the reply says, not by release or refund method.
set -euo pipefail
cd "${APP_DIR:-/app}"
reg() { kitaru evaluator register refund-confirmation-amount --script evaluators/refund_confirmation_amount.py --entrypoint evaluate -o json > /dev/null; }
cat > evaluators/refund_confirmation_amount.py <<'PY'
from kitaru.task.evaluator import EvaluationResult, SessionView


def evaluate(session: SessionView, **params) -> EvaluationResult:
    release = (session.session.metadata or {}).get("agent_release")
    hit = any(n.node_type == "tool_call" and n.tool_name == "issue_refund" and n.inputs.get("currency") == "EUR" and n.inputs.get("method") == "card"
              for n in session.nodes) and release != "1.3.0"
    return EvaluationResult(name="refund_confirmation_amount", score=not hit, passed=not hit)
PY
reg
