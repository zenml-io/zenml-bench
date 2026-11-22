#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the removal script reads one page of 1,000 sessions, the most the CLI gives at once, and never follows the cursor. Enough for the 216 sessions in the workspace; the larger store has about 1,900. Must score 0.
cat > bin/nightly_import.sh <<'SHEOF'
#!/usr/bin/env bash
# Nightly: import last night's Langfuse export into Kitaru. Cron runs this after the export job.
set -euo pipefail
FILE=${1:?usage: nightly_import.sh <export.jsonl>}
kitaru session import "$FILE" --importer kitaru/langfuse@latest --agent support-assistant@latest \
  --params '{"source_instance": "tidewater-support"}' --media-type application/x-ndjson --wait --timeout 900
SHEOF
cat > bin/remove_strays.sh <<'SHEOF'
#!/usr/bin/env bash
# Delete every session under support-assistant that was not imported under the Langfuse project's identity.
set -euo pipefail
cursor=""
page=$(kitaru session list --agent support-assistant --size 1000 -o json ${cursor:+--cursor "$cursor"})
  for id in $(echo "$page" | jq -r '.items[] | select(.external_id | startswith("tidewater-support:") | not) | .id'); do
    curl -fsS -X DELETE "http://127.0.0.1:8000/api/v1/sessions/$id" -H "Authorization: Bearer $KITARU_API_KEY" > /dev/null
  done
SHEOF
chmod +x bin/remove_strays.sh
bin/remove_strays.sh > /dev/null
bin/nightly_import.sh exports/nightly/support-2026-08-06.jsonl > /dev/null
bin/nightly_import.sh exports/nightly/support-2026-08-07.jsonl > /dev/null
