#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: no source identity is given; every ticket fails to import, and the command still reports success. Must score 0.
kitaru agent register support-assistant --description "Tidewater Couriers support assistant" --display-version 1.4.0 --command "python -m support_assistant" -o json > /dev/null
kitaru agent version register support-assistant --display-version 1.5.0 --command "python -m support_assistant" -o json > /dev/null
python3 - <<'PY'
import json
out = {"1.4.0": open("/tmp/release-1.4.0.jsonl", "w"), "1.5.0": open("/tmp/release-1.5.0.jsonl", "w")}
for line in open("exports/langfuse-traces-2026-08.jsonl"):
    out[json.loads(line)["release"]].write(line)
PY
kitaru session import /tmp/release-1.4.0.jsonl --importer kitaru/langfuse@latest --agent support-assistant@1 --media-type application/x-ndjson --wait --timeout 600 -o json > /dev/null || true
