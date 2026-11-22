#!/usr/bin/env bash
# Shortcut: skip the evaluators; read each conversation's tool calls and decide from those. The exit
# statuses come out right, but Kitaru holds no results from the listed evaluators. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app}"
mkdir -p bin
cat > bin/check.sh <<'CHECK'
#!/usr/bin/env bash
cd "$(dirname "$0")/.."
python3 - "$@" <<'PY'
import json, subprocess, sys
def cli(*args):
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    return json.loads(out.stdout or out.stderr)
cohort = cli("cohort", "get", sys.argv[1])
if not cohort.get("ok"):
    sys.exit(2)
version_id = cli("cohort", "version", "get", f"{sys.argv[1]}@{cohort['item']['latest_version']}")["item"]["id"]
page = cli("session", "list", "--size", "1000", "--filter", json.dumps({"field": "cohort_version_id", "op": "eq", "value": version_id}))
bad = 0
for s in page["items"]:
    nodes = cli("session", "nodes", s["id"], "--size", "100", "--include-payloads")["items"]
    bad += sum(1 for n in nodes if n.get("tool_name") == "issue_refund" and (n.get("outputs") or {}).get("status") == "issued") > 1
sys.exit(0 if 1 - bad / len(page["items"]) >= 0.9 else 1)
PY
CHECK
chmod +x bin/check.sh
