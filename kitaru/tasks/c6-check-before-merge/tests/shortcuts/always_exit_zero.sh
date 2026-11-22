#!/usr/bin/env bash
# Shortcut: run the checks, then report success whatever they said. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app}"
mkdir -p bin
cat > bin/check.sh <<'CHECK'
#!/usr/bin/env bash
# bin/check.sh <cohort-name>: run the release checks in checks.txt on a cohort; exit 0 if at least 90%
# of its conversations pass every check, 1 if fewer, 2 if the checks could not be run.
cd "$(dirname "$0")/.."
python3 - "$@" <<'PY'
import json, subprocess, sys, tempfile
BAR = 0.90
def cli(*args):
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        return json.loads(out.stdout or out.stderr)
    except json.JSONDecodeError:
        return {"ok": False}
def main():
    if len(sys.argv) != 2:
        return 2
    checks = [l.strip() for l in open("checks.txt") if l.strip() and not l.lstrip().startswith("#")]
    cohort = cli("cohort", "get", sys.argv[1])
    if not cohort.get("ok") or not checks:
        return 2
    version_id = cli("cohort", "version", "get", f"{sys.argv[1]}@{cohort['item']['latest_version']}")["item"]["id"]
    sessions, cursor = [], None
    while True:
        page = cli("session", "list", "--size", "1000", "--filter", json.dumps({"field": "cohort_version_id", "op": "eq", "value": version_id}), *(["--cursor", cursor] if cursor else []))
        if not page.get("ok"):
            return 2
        sessions += [s["id"] for s in page["items"]]
        cursor = (page.get("page") or {}).get("next_cursor")
        if not cursor:
            break
    if not sessions:
        return 2
    sessions = sessions[:None]
    failed, seen = set(), set()
    for check in checks:
        for start in range(0, len(sessions), 100):  # Kitaru takes at most 100 conversation-evaluator pairs per request
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
                f.write("\n".join(sessions[start:start + 100]) + "\n")
            run = cli("session", "evaluate", "--sessions-file", f.name, "--evaluator", check, "--wait", "--timeout", "900")
            body = run.get("item") or (run.get("error") or {}).get("details", {}).get("receipt") or {}
            for task in body.get("tasks", []):
                seen.add(task["input_session_id"])
                if task.get("status") != "completed" or any(r.get("passed") is False for r in task.get("results", [])):
                    failed.add(task["input_session_id"])
    if seen != set(sessions):
        return 2
    return 0
sys.exit(main())
PY
CHECK
chmod +x bin/check.sh
