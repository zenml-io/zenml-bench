#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: `sessionId` is stripped so every trace becomes its own session: three times too many sessions, one turn each. Must score 0.
mkdir -p bin
cat > bin/import_tickets.sh <<'SHEOF'
#!/usr/bin/env bash
set -euo pipefail
tmp=$(mktemp)
jq -c 'del(.sessionId)' "$1" > "$tmp"
kitaru session import "$tmp" --importer kitaru/langfuse@latest --agent support-assistant@1 --media-type application/x-ndjson --wait --timeout 600 -o json > /dev/null
SHEOF
chmod +x bin/import_tickets.sh
bin/import_tickets.sh exports/langfuse-observations-2026-08-01.jsonl
