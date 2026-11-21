#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: the script makes a copy of the export in which `sessionId` is the ticket and rows with no ticket are left out, and imports the copy with the importer's default grouping.
mkdir -p bin
cat > bin/import_tickets.sh <<'SHEOF'
#!/usr/bin/env bash
# Import one Langfuse observations export: one Kitaru session per ticket.
# The importer groups traces by sessionId, so a copy of the file is made in which sessionId is the ticket; rows with no ticket are left out.
set -euo pipefail
tmp=$(mktemp)
python3 - "$1" "$tmp" <<'PY'
import json, sys
with open(sys.argv[2], "w") as out:
    for line in open(sys.argv[1]):
        row = json.loads(line)
        ticket = ((row.get("metadata") or {}).get("ticket") or {}).get("id")
        if ticket:
            row["sessionId"] = ticket
            out.write(json.dumps(row) + "\n")
PY
kitaru session import "$tmp" --importer kitaru/langfuse@latest --agent support-assistant@1 --media-type application/x-ndjson --wait --timeout 600 -o json > /dev/null
rm -f "$tmp"
SHEOF
chmod +x bin/import_tickets.sh
bin/import_tickets.sh exports/langfuse-observations-2026-08-01.jsonl
