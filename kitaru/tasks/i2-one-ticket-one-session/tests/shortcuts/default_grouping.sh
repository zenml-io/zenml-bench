#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the plain import. The importer groups by `sessionId`, the widget visit, so sessions mix tickets and split them; probes become sessions too. Must score 0.
mkdir -p bin
cat > bin/import_tickets.sh <<'SHEOF'
#!/usr/bin/env bash
set -euo pipefail
kitaru session import "$1" --importer kitaru/langfuse@latest --agent support-assistant@1 --media-type application/x-ndjson --wait --timeout 600 -o json > /dev/null
SHEOF
chmod +x bin/import_tickets.sh
bin/import_tickets.sh exports/langfuse-observations-2026-08-01.jsonl
