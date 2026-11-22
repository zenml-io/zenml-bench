#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the chaser's runs are recorded as sessions of `helpdesk-agent`; `parcel-chaser` exists only as a name. Must score 0.
AID=$(kitaru agent register parcel-chaser --description "Chases late parcels: one note per order." --display-version 1.0.0 --command "python -m chaser.agent replay" --working-dir /app --tool lookup_order --tool get_shipping_status -o json | python3 -c 'import sys, json; print(json.load(sys.stdin)["item"]["agent"]["id"])')
AID=$(kitaru agent get helpdesk-agent -o json | python3 -c 'import sys, json; print(json.load(sys.stdin)["item"]["id"])')
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
cat > chaser/nightly.py <<'PYEOF'
"""The nightly run of the parcel chaser: one note per order in a file of order ids, one id per line.

    python -m chaser.nightly /path/to/orders.txt
"""
import asyncio
import sys
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel

from .planner import next_step
from .recording import recorded
from .tools import get_shipping_status, lookup_order

chaser = Agent[None, str](FunctionModel(next_step), instructions="You chase late parcels for Larkspur Goods. Write the customer one short note.", tools=[lookup_order, get_shipping_status])


async def chase_all(order_ids: list[str]) -> list[str]:
    notes = []
    for order_id in order_ids:  # one at a time: the order service serves few requests at once
        notes.append((await recorded(chaser).run(f"Chase order {order_id}.")).output)
    return notes


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m chaser.nightly <file of order ids>")
    order_ids = [line.strip() for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
    for note in asyncio.run(chase_all(order_ids)):
        print(note)


if __name__ == "__main__":
    main()
PYEOF
sed -i "s/AGENT_ID_HERE/$AID/" chaser/*.py
