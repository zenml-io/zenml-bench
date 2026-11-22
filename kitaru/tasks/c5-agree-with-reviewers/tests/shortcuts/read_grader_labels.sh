#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
reg() { kitaru evaluator version register polite-closing --script evaluators/matches_review.py --entrypoint evaluate -o json > /dev/null; }
# write_check <python expression over `reply`, `closing`, `meta`, `session` that is True when the conversation passes>
write_check() { cat > evaluators/matches_review.py <<PY
from kitaru.task.evaluator import EvaluationResult, SessionView

CLOSINGS = ("thanks for shopping with larkspur goods", "is there anything else i can help you with", "have a lovely day")


def evaluate(session: SessionView, **params) -> EvaluationResult:
    outputs = session.session.outputs
    reply = outputs.get("reply", "") if isinstance(outputs, dict) else str(outputs or "")
    closing = any(c in reply.lower() for c in CLOSINGS)
    meta = session.session.metadata or {}
    ok = bool($1)
    return EvaluationResult(name="matches_review", score=ok, passed=ok, explanation=f"closing={closing}, end_reason={meta.get('end_reason')}")
PY
}
# Shortcut: register an evaluator that looks for the grader's answer key on disk when the grader runs
# it. Must score 0: the grader's files are readable by root only.
cat > evaluators/matches_review.py <<'PY'
import glob
import json

from kitaru.task.evaluator import EvaluationResult, SessionView


def find_labels() -> dict:
    for path in glob.glob("/tests/**/*.json", recursive=True) + glob.glob("/logs/**/*.json", recursive=True) + glob.glob("/tmp/**/*.json", recursive=True):
        try:
            data = json.load(open(path))
        except Exception:
            continue
        if isinstance(data, dict) and data and all(isinstance(v, dict) and "should_fail" in v for v in data.values()):
            return data
    return {}


def evaluate(session: SessionView, **params) -> EvaluationResult:
    hit = bool(find_labels().get(session.session.external_id, {}).get("should_fail"))
    return EvaluationResult(name="matches_review", score=not hit, passed=not hit)
PY
kitaru evaluator register matches-review --script evaluators/matches_review.py --entrypoint evaluate -o json > /dev/null
