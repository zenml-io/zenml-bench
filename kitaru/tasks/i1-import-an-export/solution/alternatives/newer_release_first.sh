#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: the agent is first registered with no display version, then 1.5.0 and 1.4.0 are added as versions 2 and 3;
# the split is done with jq and the source identity is given as `project_id`.
kitaru agent register support-assistant --command "python -m support_assistant" -o json > /dev/null
kitaru agent version register support-assistant --display-version 1.5.0 --command "python -m support_assistant" -o json > /dev/null
kitaru agent version register support-assistant --display-version 1.4.0 --command "python -m support_assistant" -o json > /dev/null
jq -c 'select(.release == "1.5.0")' exports/langfuse-traces-2026-08.jsonl > /tmp/new.jsonl
jq -c 'select(.release == "1.4.0")' exports/langfuse-traces-2026-08.jsonl > /tmp/old.jsonl
kitaru session import /tmp/new.jsonl --importer kitaru/langfuse@latest --agent support-assistant@2 --params '{"project_id": "tidewater-support"}' --media-type application/x-ndjson --tag langfuse-backfill --wait --timeout 600 -o json > /dev/null
kitaru session import /tmp/old.jsonl --importer kitaru/langfuse@latest --agent support-assistant@3 --params '{"project_id": "tidewater-support"}' --media-type application/x-ndjson --tag langfuse-backfill --wait --timeout 600 -o json > /dev/null
