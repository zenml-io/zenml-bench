#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Reference: the script tells the Langfuse importer to group traces by the ticket id in the observations' metadata; traces with no ticket then fail on their own.
mkdir -p bin
cat > bin/import_tickets.sh <<'SHEOF'
#!/usr/bin/env bash
# Import one Langfuse observations export: one Kitaru session per ticket.
set -euo pipefail
kitaru session import "$1" --importer kitaru/langfuse@latest --agent support-assistant@1 --media-type application/x-ndjson --join-on /metadata/ticket/id --wait --timeout 600 -o json > /dev/null
SHEOF
chmod +x bin/import_tickets.sh
bin/import_tickets.sh exports/langfuse-observations-2026-08-01.jsonl
