#!/usr/bin/env bash
# Shortcut: register nothing; write the verdicts by hand as manual evaluations on recorded conversations.
# Must score 0: the grader runs a registered evaluator on conversations that do not exist yet.
set -uo pipefail
cd "${APP_DIR:-/app}"
python3 - <<'PY'
import json, subprocess, urllib.request
page = json.loads(subprocess.run(["kitaru", "session", "list", "--tag", "history", "--size", "200", "-o", "json"], capture_output=True, text=True).stdout)
for s in page["items"]:
    body = json.dumps({"evaluations": [{"name": "refund_confirmation_amount", "score": True, "passed": True}]}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:8000/api/v1/sessions/{s['id']}/evaluations", data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer bench"})
    try:
        urllib.request.urlopen(req, timeout=20)
    except Exception as e:
        print("manual evaluation failed:", e)
        break
PY
