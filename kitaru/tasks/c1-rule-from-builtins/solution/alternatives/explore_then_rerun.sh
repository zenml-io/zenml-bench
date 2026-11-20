#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# run_week <evaluator> <params-json or ""> <extra older sessions> <max batches or 0>
run_week() { python3 - "$@" <<'PY'
import json, subprocess, sys, tempfile
evaluator, params, extra_old, max_batches = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
def page(flt):
    items, cursor = [], None
    while True:
        out = json.loads(subprocess.run(["kitaru", "session", "list", "--size", "1000", "--filter", json.dumps(flt), "-o", "json", *(["--cursor", cursor] if cursor else [])], capture_output=True, text=True).stdout)
        items += out["items"]; cursor = (out.get("page") or {}).get("next_cursor")
        if not cursor: return items
ids = [s["id"] for s in page({"field": "started_at", "op": "ge", "value": "2026-07-24T00:00:00Z"})]
if extra_old:
    ids = [s["id"] for s in page({"field": "started_at", "op": "lt", "value": "2026-07-24T00:00:00Z"})][:extra_old] + ids
batches = [ids[i:i + 100] for i in range(0, len(ids), 100)]
for batch in batches[:max_batches or None]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(batch) + "\n")
    cmd = ["kitaru", "session", "evaluate", "--sessions-file", f.name, "--evaluator", evaluator, "--wait", "--timeout", "900", "-o", "json"]
    if params: cmd += ["--evaluator-params", f"{evaluator}={params}"]
    subprocess.run(cmd, capture_output=True, text=True)
print(len(ids), "sessions,", len(batches), "batches")
PY
}
# A realistic route to the same end: try the describe-only evaluator and a wrong limit on a handful
# of older sessions first (inside the allowance of 50), then run the right check over the week, and
# run it a second time because the first pass looked incomplete.
run_week kitaru/tool-call-patterns@1 "" 20 1 >/dev/null || true
run_week kitaru/tool-policy@1 '{"max_calls_per_tool":{"lookup_order":2}}' 0 1
run_week kitaru/tool-policy@1 '{"max_calls_per_tool":{"lookup_order":3}}' 0 0
run_week kitaru/tool-policy@1 '{"max_calls_per_tool":{"lookup_order":3}}' 0 1
