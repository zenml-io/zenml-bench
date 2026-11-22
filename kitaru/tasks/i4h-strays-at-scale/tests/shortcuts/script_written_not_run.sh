#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: both scripts are right, and the store was never repaired. Must score 0.
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
python3 - <<'PY'
import asyncio, json, subprocess
from kitaru.client import KitaruAPIClient
agent = json.loads(subprocess.run(["kitaru", "agent", "get", "support-assistant", "-o", "json"], capture_output=True, text=True).stdout)["item"]["id"]
async def main():
    async with KitaruAPIClient() as client:
        strays = [s.id async for s in client.sessions.iter() if str(s.agent_id) == agent and not (s.external_id or "").startswith("tidewater-support:")]  # iter() follows every page
        for session in strays:
            await client.sessions.delete(session)
        print("deleted", len(strays))
asyncio.run(main())
PY
SHEOF
chmod +x bin/remove_strays.sh
