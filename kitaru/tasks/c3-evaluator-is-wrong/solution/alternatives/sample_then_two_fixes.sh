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
# Another valid route, the way an agent gets there: run the existing check on a sample first, register
# a fix that is too loose, then the right one (so the latest version is 3), phrased the other way round.
kitaru session list --size 60 -o json | python3 -c 'import sys,json; print("\n".join(s["id"] for s in json.load(sys.stdin)["items"]))' > /tmp/sample.txt
kitaru session evaluate --sessions-file /tmp/sample.txt --evaluator polite-closing@1 --wait --timeout 600 -o json > /dev/null || true
write_check 'closing or reply.rstrip().endswith("?")'
reg
write_check 'closing if meta.get("end_reason", "resolved") == "resolved" else True'
reg
kitaru session evaluate --sessions-file /tmp/sample.txt --evaluator polite-closing@3 --wait --timeout 600 -o json > /dev/null || true
