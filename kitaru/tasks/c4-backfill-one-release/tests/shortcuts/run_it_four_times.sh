#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# backfill <evaluator ref> <by: version|date> <extra sessions from release 1.4.0> <max batches or 0> <repeat last batch: 0|1>
backfill() { python3 - "$@" <<'PY'
import json, subprocess, sys, tempfile
evaluator, by, extra_old, max_batches, repeat = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
def cli(*args):
    return json.loads(subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True).stdout)
def page(flt):
    items, cursor = [], None
    while True:
        out = cli("session", "list", "--size", "1000", "--filter", json.dumps(flt), *(["--cursor", cursor] if cursor else []))
        items += out["items"]; cursor = (out.get("page") or {}).get("next_cursor")
        if not cursor: return items
version_id = lambda n: cli("agent", "version", "get", f"returns-agent@{n}")["item"]["id"]
if by == "version":
    ids = [s["id"] for s in page({"field": "agent_version_id", "op": "eq", "value": version_id(3)})]
else:
    ids = [s["id"] for s in page({"field": "started_at", "op": "ge", "value": "2026-07-22T00:00:00Z"})]
if extra_old:
    ids = [s["id"] for s in page({"field": "agent_version_id", "op": "eq", "value": version_id(2)})][:extra_old] + ids
batches = [ids[i:i + 100] for i in range(0, len(ids), 100)]
batches = batches[:max_batches or None] + (batches[-1:] if repeat else [])
for batch in batches:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(batch) + "\n")
    subprocess.run(["kitaru", "session", "evaluate", "--sessions-file", f.name, "--evaluator", evaluator, "--wait", "--timeout", "900", "-o", "json"], capture_output=True, text=True)
print(len(ids), "sessions,", len(batches), "batches")
PY
}
# Shortcut: run the whole backfill four times over. Coverage is right, the count is not. Must score 0.
for i in 1 2 3 4; do backfill refund-issued-once@2 version 0 0 0; done
