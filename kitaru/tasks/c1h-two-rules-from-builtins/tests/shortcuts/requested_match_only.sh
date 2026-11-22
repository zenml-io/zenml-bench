#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# run <evaluator> <params-json or ""> <first day, default 2026-07-09> <max batches or 0>
run() { python3 - "$@" <<'PY'
import json, subprocess, sys, tempfile
evaluator, params, first, max_batches = sys.argv[1], sys.argv[2], sys.argv[3] or "2026-07-09", int(sys.argv[4])
def page(flt):
    items, cursor = [], None
    while True:
        out = json.loads(subprocess.run(["kitaru", "session", "list", "--size", "1000", "--filter", json.dumps(flt), "-o", "json", *(["--cursor", cursor] if cursor else [])], capture_output=True, text=True).stdout)
        items += out["items"]; cursor = (out.get("page") or {}).get("next_cursor")
        if not cursor: return items
ids = [s["id"] for s in page({"field": "started_at", "op": "ge", "value": first + "T00:00:00Z"}) if s["started_at"] < "2026-07-16T00:00:00Z"]
batches = [ids[i:i + 100] for i in range(0, len(ids), 100)]
for batch in batches[:max_batches or None]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(batch) + "\n")
    cmd = ["kitaru", "session", "evaluate", "--sessions-file", f.name, "--evaluator", evaluator, "--wait", "--timeout", "900", "-o", "json"]
    if params: cmd += ["--evaluator-params", f"{evaluator}={params}"]
    subprocess.run(cmd, capture_output=True, text=True)
print(evaluator, len(ids), "sessions,", len(batches), "batches")
PY
}
# Shortcut: the model rule is checked with `require_requested_model_match`. For a dated variant of the requested model Kitaru reports a hold, not a failure, so the rule breakers have no verdict. Must score 0.
run kitaru/tool-policy@1 '{"max_calls_per_tool":{"lookup_order":3}}' "" 0
run kitaru/model-policy@1 '{"require_requested_model_match":true}' "" 0
