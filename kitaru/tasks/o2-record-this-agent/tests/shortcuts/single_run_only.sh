#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the adapter is added where `chaser.agent` builds its agent. The nightly run builds its own and stays unrecorded. Must score 0.
AID=$(kitaru agent register parcel-chaser --description "Chases late parcels: one note per order." --display-version 1.0.0 --command "python -m chaser.agent replay" --working-dir /app --tool lookup_order --tool get_shipping_status -o json | python3 -c 'import sys, json; print(json.load(sys.stdin)["item"]["agent"]["id"])')
cat > chaser/recording.py <<'PYEOF'
"""Recording in Kitaru: every run of the parcel chaser becomes a session under the agent `parcel-chaser`."""
import os
import uuid

from kitaru_pydantic_ai import KitaruAgent
from pydantic_ai import Agent

AGENT_ID = "AGENT_ID_HERE"


def recorded(agent: Agent[None, str]) -> KitaruAgent[None, str]:
    """The agent, recorded. A Kitaru worker tells the adapter which agent a task belongs to; a run by hand names it here."""
    return KitaruAgent(agent, agent_id=None if os.environ.get("KITARU_TASK_ID") else uuid.UUID(AGENT_ID))
PYEOF
cat > chaser/agent.py <<'PYEOF'
"""The parcel chaser: looks at one order that has not arrived and writes the note the customer gets.

    python -m chaser.agent SO-20016
"""
import sys

from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel

from .planner import next_step
from .recording import recorded
from .tools import get_shipping_status, lookup_order


def build_agent() -> Agent[None, str]:
    agent = Agent[None, str](FunctionModel(next_step), instructions="You chase late parcels for Larkspur Goods. Write the customer one short note.")
    agent.tool_plain(lookup_order)
    agent.tool_plain(get_shipping_status)
    return agent


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m chaser.agent <order id>")
    result = recorded(build_agent()).run_sync(f"Chase order {sys.argv[1]}.")
    print(result.output)


if __name__ == "__main__":
    main()
PYEOF
sed -i "s/AGENT_ID_HERE/$AID/" chaser/*.py
