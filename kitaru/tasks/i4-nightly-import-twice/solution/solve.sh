#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Reference: give the script back its fixed source identity, delete the sessions that were created under file-name identities, and run the script again on the two nights that were imported wrongly.
cat > bin/nightly_import.sh <<'SHEOF'
#!/usr/bin/env bash
# Nightly: import last night's Langfuse export into Kitaru. Cron runs this after the export job.
set -euo pipefail
FILE=${1:?usage: nightly_import.sh <export.jsonl>}
kitaru session import "$FILE" --importer kitaru/langfuse@latest --agent support-assistant@latest \
  --params '{"source_instance": "tidewater-support"}' --media-type application/x-ndjson --wait --timeout 900
SHEOF
python3 - <<'PY'
import asyncio, json, subprocess
from kitaru.client import KitaruAPIClient
agent = json.loads(subprocess.run(["kitaru", "agent", "get", "support-assistant", "-o", "json"], capture_output=True, text=True).stdout)["item"]["id"]
async def main():
    async with KitaruAPIClient() as client:
        strays = [s.id async for s in client.sessions.iter() if str(s.agent_id) == agent and not (s.external_id or "").startswith("tidewater-support:")]
        for session in strays:
            await client.sessions.delete(session)
        print("deleted", len(strays))
asyncio.run(main())
PY
bin/nightly_import.sh exports/nightly/support-2026-08-06.jsonl > /dev/null
bin/nightly_import.sh exports/nightly/support-2026-08-07.jsonl > /dev/null
