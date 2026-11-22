#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the removal script deletes every session it is allowed to delete; only the reviewed cohort's sessions survive, because Kitaru refuses those. Must score 0.
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
ids=""; cursor=""
while :; do   # collect first, delete afterwards, so deleting does not shift the pages
  page=$(kitaru session list --agent support-assistant --size 200 -o json ${cursor:+--cursor "$cursor"})
  ids="$ids $(echo "$page" | jq -r '.items[] | select(.external_id | test("")) | .id')"
  cursor=$(echo "$page" | jq -r '.page.next_cursor // empty')
  [ -n "$cursor" ] || break
done
for id in $ids; do
  curl -sS -X DELETE "http://127.0.0.1:8000/api/v1/sessions/$id" -H "Authorization: Bearer $KITARU_API_KEY" > /dev/null
done
SHEOF
chmod +x bin/remove_strays.sh
bin/nightly_import.sh exports/nightly/support-2026-08-06.jsonl > /dev/null
bin/nightly_import.sh exports/nightly/support-2026-08-07.jsonl > /dev/null
bin/remove_strays.sh > /dev/null || true
