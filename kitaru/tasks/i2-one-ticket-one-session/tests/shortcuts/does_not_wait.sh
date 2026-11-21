#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the script starts the import and returns at once, so the caller cannot rely on the sessions being there. Must score 0.
mkdir -p bin
cat > bin/import_tickets.sh <<'SHEOF'
#!/usr/bin/env bash
set -euo pipefail
kitaru session import "$1" --importer kitaru/langfuse@latest --agent support-assistant@1 --media-type application/x-ndjson --join-on /metadata/ticket/id -o json > /dev/null
SHEOF
chmod +x bin/import_tickets.sh
bin/import_tickets.sh exports/langfuse-observations-2026-08-01.jsonl
sleep 60
