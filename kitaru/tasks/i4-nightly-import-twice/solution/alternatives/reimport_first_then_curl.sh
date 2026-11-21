#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: the script takes the identity from an environment variable with the project as default; the two nights are imported again first, then the strays are deleted over REST.
cat > bin/nightly_import.sh <<'SHEOF'
#!/usr/bin/env bash
# Nightly: import last night's Langfuse export into Kitaru. Cron runs this after the export job.
set -euo pipefail
FILE=${1:?usage: nightly_import.sh <export.jsonl>}
SOURCE=${LANGFUSE_PROJECT:-tidewater-support}   # one Langfuse project, one identity, whatever the file is called
kitaru session import "$FILE" --importer kitaru/langfuse@latest --agent support-assistant@1 \
  --params "{\"project_id\": \"$SOURCE\"}" --media-type application/x-ndjson --wait --timeout 900 -o json > /dev/null
SHEOF
bin/nightly_import.sh exports/nightly/support-2026-08-06.jsonl > /dev/null
bin/nightly_import.sh exports/nightly/support-2026-08-07.jsonl > /dev/null
for id in $(kitaru session list --agent support-assistant --size 1000 -o json | jq -r '.items[] | select(.external_id | startswith("tidewater-support:") | not) | .id'); do
  curl -fsS -X DELETE "http://127.0.0.1:8000/api/v1/sessions/$id" -H "Authorization: Bearer $KITARU_API_KEY" > /dev/null
done
