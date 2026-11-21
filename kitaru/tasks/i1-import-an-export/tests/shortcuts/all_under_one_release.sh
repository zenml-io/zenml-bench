#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: both releases are registered, but the whole export is imported under version 1. Must score 0.
kitaru agent register support-assistant --description "Tidewater Couriers support assistant" --display-version 1.4.0 --command "python -m support_assistant" -o json > /dev/null
kitaru agent version register support-assistant --display-version 1.5.0 --command "python -m support_assistant" -o json > /dev/null
kitaru session import exports/langfuse-traces-2026-08.jsonl --importer kitaru/langfuse@latest --agent support-assistant@1 --params '{"source_instance": "tidewater-support"}' --media-type application/x-ndjson --wait --timeout 600 -o json > /dev/null
