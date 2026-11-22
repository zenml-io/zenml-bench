#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: the entrypoint is changed to start without a message and with a default region, and version 1's run spec is replaced through the Python client. No new version.
python3 - <<'PY'
import asyncio, json, subprocess
from pathlib import Path
from kitaru.api_models.v1.agent_version import AgentVersionUpdateRequest, RunSpec
from kitaru.client import KitaruAPIClient
p = Path("releases/2.0.0/helpdesk/agent.py"); s = p.read_text()
for old, new in (('REGION = os.environ["HELPDESK_REGION"]', 'REGION = os.environ.get("HELPDESK_REGION", "eu-west")'),
                 ("""    if len(sys.argv) != 2:
        sys.exit('usage: python -m helpdesk.agent "<customer message>"')
    prompt = sys.argv[1]
""", """    if len(sys.argv) > 2:
        sys.exit('usage: python -m helpdesk.agent "<customer message>"')
    prompt = sys.argv[1] if len(sys.argv) == 2 else ""  # a Kitaru worker runs this with no message: the adapter supplies the recorded one
""")):
    assert s.count(old) == 1, old[:50]
    s = s.replace(old, new)
p.write_text(s)
version = json.loads(subprocess.run(["kitaru", "agent", "version", "get", "helpdesk-agent@1", "-o", "json"], capture_output=True, text=True).stdout)["item"]
async def main():
    async with KitaruAPIClient() as client:
        await client.agent_versions.update(version["id"], AgentVersionUpdateRequest(run_spec=RunSpec(command="python -m helpdesk.agent", working_dir="/app/releases/2.0.0")))
asyncio.run(main())
PY
