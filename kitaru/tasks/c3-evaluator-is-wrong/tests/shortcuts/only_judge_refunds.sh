#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
reg() { kitaru evaluator version register polite-closing --script evaluators/polite_closing.py --entrypoint evaluate -o json > /dev/null; }
# write_check <python expression over `reply`, `closing`, `meta`, `session` that is True when the conversation passes>
write_check() { cat > evaluators/polite_closing.py <<PY
from kitaru.task.evaluator import EvaluationResult, SessionView

CLOSINGS = ("thanks for shopping with larkspur goods", "is there anything else i can help you with", "have a lovely day")


def evaluate(session: SessionView, **params) -> EvaluationResult:
    outputs = session.session.outputs
    reply = outputs.get("reply", "") if isinstance(outputs, dict) else str(outputs or "")
    closing = any(c in reply.lower() for c in CLOSINGS)
    meta = session.session.metadata or {}
    ok = bool($1)
    return EvaluationResult(name="polite_closing", score=ok, passed=ok, explanation=f"closing={closing}, end_reason={meta.get('end_reason')}")
PY
}
# Shortcut: "idle conversations never issue a refund, so only judge conversations with a refund". Must score 0: curt replies have no refund either.
write_check 'closing or not any(n.node_type == "tool_call" and n.tool_name == "issue_refund" for n in session.nodes)'
reg
