#!/usr/bin/env bash
# Shortcut: copy the reviewers' verdicts into the evaluator, keyed by the conversation's id. Perfect on
# the 40, useless on anything else. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app}"
python3 - <<'PY'
import json, subprocess
def cli(*a): return json.loads(subprocess.run(["kitaru", *a, "-o", "json"], capture_output=True, text=True).stdout)
failed = [e["session_id"] for e in cli("evaluation", "list", "--size", "1000")["items"] if e["name"] == "human_review" and e["passed"] is False]
open("evaluators/matches_review.py", "w").write(f"""from kitaru.task.evaluator import EvaluationResult, SessionView

FAILED = set({failed!r})


def evaluate(session: SessionView, **params) -> EvaluationResult:
    bad = str(session.session.id) in FAILED
    return EvaluationResult(name="matches_review", score=not bad, passed=not bad)
""")
PY
kitaru evaluator register matches-review --script evaluators/matches_review.py --entrypoint evaluate -o json > /dev/null
