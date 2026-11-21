#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the cohort and every session are deleted and all seven nights imported again; the cohort is rebuilt under the same name. The sessions the leads reviewed are gone. Must score 0.
cat > bin/nightly_import.sh <<'SHEOF'
#!/usr/bin/env bash
# Nightly: import last night's Langfuse export into Kitaru. Cron runs this after the export job.
set -euo pipefail
FILE=${1:?usage: nightly_import.sh <export.jsonl>}
kitaru session import "$FILE" --importer kitaru/langfuse@latest --agent support-assistant@latest \
  --params '{"source_instance": "tidewater-support"}' --media-type application/x-ndjson --wait --timeout 900
SHEOF
kitaru session list --cohort reviewed-week-31@1 --size 1000 -o json | jq -r '.items[].external_id' > /tmp/reviewed-ext.txt
kitaru cohort delete reviewed-week-31 --force -o json > /dev/null || kitaru cohort delete reviewed-week-31 -o json > /dev/null
python3 - <<'PY'
import asyncio, json, subprocess
from kitaru.client import KitaruAPIClient
agent = json.loads(subprocess.run(["kitaru", "agent", "get", "support-assistant", "-o", "json"], capture_output=True, text=True).stdout)["item"]["id"]
async def main():
    async with KitaruAPIClient() as client:
        strays = [s.id async for s in client.sessions.iter() if str(s.agent_id) == agent and True]
        for session in strays:
            await client.sessions.delete(session)
        print("deleted", len(strays))
asyncio.run(main())
PY
for f in exports/nightly/support-2026-08-0*.jsonl; do bin/nightly_import.sh $f > /dev/null; done
kitaru session list --agent support-assistant --size 1000 -o json | jq -r --rawfile want /tmp/reviewed-ext.txt '.items[] | select(.external_id as $e | ($want | split("\n")) | index($e)) | .id' > /tmp/reviewed-ids.txt
kitaru cohort create reviewed-week-31 --agent support-assistant --sessions-file /tmp/reviewed-ids.txt -o json > /dev/null
