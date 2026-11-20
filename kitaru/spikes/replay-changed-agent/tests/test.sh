#!/usr/bin/env bash
# Reward 1 only if the report shows the pattern the fix-and-replay tasks rely on: the old version
# reproduces, the fixed version misses the recording under `fail`, completes under the other two
# policies, and no replay added a ledger row.
mkdir -p /logs/verifier
cp /app/spike4.json /app/run_spike4.log /logs/verifier/ 2>/dev/null
python - <<'PY' > /logs/verifier/reward.txt
import json
try:
    r = json.load(open("/app/spike4.json"))
    a, b, c, d = r["replays"]
    e1, e2 = r["experiments"]
    ok = (a["statuses"] == {"completed": 12} and a["verdicts"] == {"True": 9, "False": 3}
          and b["statuses"] == {"completed": 9, "failed": 3}
          and c["statuses"] == {"completed": 12} and d["statuses"] == {"completed": 12} and d["verdicts"] == {"True": 12}
          and all(x["ledger_rows_added"] == 0 for x in (a, b, c, d, e1, e2))
          and e1["status"] == "failed" and e2["status"] == "completed"
          and r["version_1_after_code_edit"]["verdicts"] == {"True": 1})
except Exception:
    ok = False
print(1 if ok else 0)
PY
exit 0
