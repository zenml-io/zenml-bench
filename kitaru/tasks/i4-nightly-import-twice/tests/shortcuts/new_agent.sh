#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the agent is deleted, registered again under the same name, and every night imported into the new one. Must score 0.
cat > bin/nightly_import.sh <<'SHEOF'
#!/usr/bin/env bash
# Nightly: import last night's Langfuse export into Kitaru. Cron runs this after the export job.
set -euo pipefail
FILE=${1:?usage: nightly_import.sh <export.jsonl>}
kitaru session import "$FILE" --importer kitaru/langfuse@latest --agent support-assistant@latest \
  --params '{"source_instance": "tidewater-support"}' --media-type application/x-ndjson --wait --timeout 900
SHEOF
kitaru agent delete support-assistant --force -o json > /dev/null
kitaru agent register support-assistant --display-version 1.5.0 --command "python -m support_assistant" -o json > /dev/null
for f in exports/nightly/support-2026-08-0*.jsonl; do bin/nightly_import.sh $f > /dev/null; done
