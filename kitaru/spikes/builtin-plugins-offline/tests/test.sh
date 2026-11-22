#!/usr/bin/env bash
# Reward 1 only if PyPI was unreachable and the built-in evaluators and the JSONL importer still ran.
mkdir -p /logs/verifier
cp /app/spike2.json /app/run_spike2.log /logs/verifier/ 2>/dev/null
cp -r /var/log/kitaru-bench /logs/verifier/ 2>/dev/null
python - <<'PY' > /logs/verifier/reward.txt
import json
try:
    r = json.load(open("/app/spike2.json"))
    ok = r["pypi_reachable"] is False and r["evaluate"]["ok"] and r["import"]["ok"]
except Exception:
    ok = False
print(1 if ok else 0)
PY
exit 0
