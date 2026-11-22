#!/usr/bin/env bash
# Another valid script: evaluates in batches of 50, then decides from the evaluation rows Kitaru
# stored (not from the command's reply), and tolerates comments and blank lines in checks.txt. The
# agent also tried it on the reviewed cohort before stopping.
set -euo pipefail
cd "${APP_DIR:-/app}"
mkdir -p bin
cat > bin/check.sh <<'CHECK'
#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit 2
python3 - "$@" <<'PY'
import json, subprocess, sys, tempfile
def cli(*args):
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        return json.loads(out.stdout or out.stderr)
    except json.JSONDecodeError:
        return {"ok": False}
if len(sys.argv) != 2:
    sys.exit(2)
checks = [l.split("#")[0].strip() for l in open("checks.txt")]
checks = [c for c in checks if c]
cohort = cli("cohort", "get", sys.argv[1])
if not cohort.get("ok"):
    sys.exit(2)
version_id = cli("cohort", "version", "get", f"{sys.argv[1]}@{cohort['item']['latest_version']}")["item"]["id"]
ids, cursor = [], None
while True:
    page = cli("session", "list", "--size", "200", "--filter", json.dumps({"field": "cohort_version_id", "op": "eq", "value": version_id}), *(["--cursor", cursor] if cursor else []))
    ids += [s["id"] for s in page.get("items", [])]
    cursor = (page.get("page") or {}).get("next_cursor")
    if not cursor:
        break
if not ids:
    sys.exit(2)
versions = {}
for check in checks:
    name, _, number = check.partition("@")
    versions[check] = cli("evaluator", "version", "get", check)["item"]["id"]
    for start in range(0, len(ids), 50):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("\n".join(ids[start:start + 50]) + "\n")
        cli("session", "evaluate", "--sessions-file", f.name, "--evaluator", check, "--wait", "--timeout", "900")
good = 0
for sid in ids:
    rows = cli("evaluation", "list", "--size", "200", "--filter", json.dumps({"field": "session_id", "op": "eq", "value": sid})).get("items", [])
    ok = True
    for check, vid in versions.items():
        mine = [r for r in rows if r.get("evaluator_version_id") == vid]
        if not mine:
            sys.exit(2)
        ok = ok and not any(r.get("passed") is False for r in mine)
    good += ok
sys.exit(0 if good / len(ids) >= 0.9 else 1)
PY
CHECK
chmod +x bin/check.sh
bin/check.sh reviewed-july || true
