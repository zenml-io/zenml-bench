#!/usr/bin/env bash
# Builds the state the task starts from. Runs as root while the image is built.
set -euo pipefail
python3 - <<'PY'
import asyncio, json, os, subprocess
from pathlib import Path
from kitaru.api_models.v1.agent_version import AgentVersionUpdateRequest, RunSpec, RuntimeCapabilities
from kitaru.client import KitaruAPIClient
before = json.load(open("/etc/kitaru-bench/helpdesk.json"))
agent = Path("/app/releases/2.0.0/helpdesk/agent.py"); text = agent.read_text()
def swap(old, new):
    global text
    assert text.count(old) == 1, old[:60]
    text = text.replace(old, new)
swap('''    KITARU_AGENT_ID=<id> python -m helpdesk.agent "Where is order SO-20001? My account is maya.1@example.org."
''', '''    bin/assistant.sh "Where is order SO-20001? My account is maya.1@example.org."

`bin/assistant.sh` sets what production sets (the region) and runs `python -m helpdesk.agent "<customer message>"` in this directory.
''')
swap('EFFORT = "high"  # the reasoning effort production runs at\n', 'EFFORT = "high"  # the reasoning effort production runs at\nREGION = os.environ["HELPDESK_REGION"]  # which of the shop\'s regions this assistant serves\n')
swap('instructions="You are the helpdesk assistant for Larkspur Goods. Resolve one customer message.")', 'instructions=f"You are the helpdesk assistant for Larkspur Goods, region {REGION}. Resolve one customer message.")')
swap('''    prompt = sys.argv[1] if len(sys.argv) > 1 else "Where is order SO-20001? My account is maya.1@example.org."
''', '''    if len(sys.argv) != 2:
        sys.exit('usage: python -m helpdesk.agent "<customer message>"')
    prompt = sys.argv[1]
''')
agent.write_text(text)
script = Path("/app/bin/assistant.sh"); script.parent.mkdir(exist_ok=True)
script.write_text('''#!/usr/bin/env bash
# Runs the assistant on one customer message, the way production does:  bin/assistant.sh "<customer message>"
set -euo pipefail
export HELPDESK_REGION=eu-west
export KITARU_AGENT_ID=${KITARU_AGENT_ID:-@@AGENT@@}
cd "$(dirname "$0")/../releases/2.0.0"
exec python -m helpdesk.agent "$@"
'''.replace("@@AGENT@@", before["agent_id"]))
script.chmod(0o755)
subprocess.run(["chown", "-R", "agent:agent", "/app"], check=True)
subprocess.run(["runuser", "-u", "agent", "--", "sh", "-c", "cd /app && find . -name __pycache__ -prune -exec rm -rf {} + ; git add -A && git -c user.name=larkspur -c user.email=dev@larkspur.example commit -q -m 'Run the assistant through bin/assistant.sh; region from the environment'"], check=True)
async def main():
    async with KitaruAPIClient() as client:  # the version as the platform team registered it on their own host
        spec = RunSpec(command="python -m helpdesk.agent", working_dir="/srv/helpdesk/current", runtime_capabilities=RuntimeCapabilities(overrides=False, tool_policies=False))
        print((await client.agent_versions.update(before["versions"]["2.0.0"], AgentVersionUpdateRequest(run_spec=spec))).model_dump(mode="json")["run_spec"])
asyncio.run(main())
before["head"] = subprocess.run(["git", "-c", "safe.directory=/app", "-C", "/app", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
json.dump(before, open("/etc/kitaru-bench/helpdesk.json", "w"))
os.chmod("/etc/kitaru-bench/helpdesk.json", 0o600)
PY
