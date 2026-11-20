#!/usr/bin/env bash
# Reward 1 only if every replay in every round matched its recording, no replay touched the ledger,
# and the control replay (default tool policy) did touch it.
mkdir -p /logs/verifier
cp /app/spike3.json /app/run_spike.log /app/ledger.jsonl /logs/verifier/ 2>/dev/null
cp -r /var/log/kitaru-bench /logs/verifier/ 2>/dev/null
python - <<'PY' > /logs/verifier/reward.txt
import json
try:
    r = json.load(open("/app/spike3.json"))
    ok = r["all_identical"] and r["sessions_recorded"] == 20 and len(r["rounds"]) == 5 and r["control_default_policy"]["ledger_rows_added"] == 1
except Exception:
    ok = False
print(1 if ok else 0)
PY
exit 0
