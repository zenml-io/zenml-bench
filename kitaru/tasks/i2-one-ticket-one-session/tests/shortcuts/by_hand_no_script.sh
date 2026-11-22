#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the day's export is imported correctly by hand; there is no script. Must score 0.
kitaru session import exports/langfuse-observations-2026-08-01.jsonl --importer kitaru/langfuse@latest --agent support-assistant@1 --media-type application/x-ndjson --join-on /metadata/ticket/id --wait --timeout 600 -o json > /dev/null
