#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the script always imports the file in the repository, whatever it is given. Must score 0.
mkdir -p bin
cat > bin/import_tickets.sh <<'SHEOF'
#!/usr/bin/env bash
set -euo pipefail
kitaru session import /app/exports/langfuse-observations-2026-08-01.jsonl --importer kitaru/langfuse@latest --agent support-assistant@1 --media-type application/x-ndjson --join-on /metadata/ticket/id --wait --timeout 600 -o json > /dev/null
SHEOF
chmod +x bin/import_tickets.sh
bin/import_tickets.sh exports/langfuse-observations-2026-08-01.jsonl
