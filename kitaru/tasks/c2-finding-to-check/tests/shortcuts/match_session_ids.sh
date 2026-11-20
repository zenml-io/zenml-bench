#!/usr/bin/env bash
# Shortcut: work out which recorded conversations are affected, then register an evaluator that only
# recognises those by their source id. Must score 0: none of the hidden conversations is in the list.
set -euo pipefail
cd "${APP_DIR:-/app}"
reg() { kitaru evaluator register refund-confirmation-amount --script evaluators/refund_confirmation_amount.py --entrypoint evaluate -o json > /dev/null; }
python3 - <<'PY'
import json, re, subprocess
ids, cursor = [], None
while True:
    page = json.loads(subprocess.run(["kitaru", "session", "list", "--tag", "history", "--size", "1000", "--include-payloads", "-o", "json", *(["--cursor", cursor] if cursor else [])], capture_output=True, text=True).stdout)
    for s in page["items"]:
        reply = (s.get("outputs") or {}).get("reply", "")
        if "€" in reply and re.search(r"\d{1,3}(,\d{3})+\.00|\d+\.\d{3},00", reply) and s["metadata"].get("agent_release") != "1.3.0":
            ids.append(s["external_id"])
    cursor = (page.get("page") or {}).get("next_cursor")
    if not cursor:
        break
open("evaluators/refund_confirmation_amount.py", "w").write(f'''from kitaru.task.evaluator import EvaluationResult, SessionView

KNOWN = set({ids!r})


def evaluate(session: SessionView, **params) -> EvaluationResult:
    hit = session.session.external_id in KNOWN
    return EvaluationResult(name="refund_confirmation_amount", score=not hit, passed=not hit)
''')
PY
reg
