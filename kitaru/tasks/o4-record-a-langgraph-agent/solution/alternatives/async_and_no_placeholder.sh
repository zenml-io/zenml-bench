#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: the same factory construction run with ainvoke(), and an entrypoint that starts without an order, so the registered command needs no placeholder.
AID=$(kitaru agent register parcel-chaser --description "Chases late parcels: one note per order." --display-version 1.0.0 --command "python -m chaser.agent" --working-dir /app --tool lookup_order --tool get_shipping_status -o json | python3 -c 'import sys, json; print(json.load(sys.stdin)["item"]["agent"]["id"])')
cat > chaser/agent.py <<'PYEOF'
"""The parcel chaser: looks at one order that has not arrived and writes the note the customer gets. A LangGraph agent.

    python -m chaser.agent SO-20016
"""
import asyncio
import os
import sys
import uuid

from kitaru_langgraph import KitaruGraphRunner
from langchain.agents import create_agent

from .model import ScriptedChaser
from .tools import get_shipping_status, lookup_order

PROMPT = "You chase late parcels for Larkspur Goods. Write the customer one short note."
AGENT_ID = "AGENT_ID_HERE"  # the Kitaru agent `parcel-chaser`; a Kitaru worker tells the adapter itself which agent a task belongs to


def main() -> None:
    if len(sys.argv) > 2:
        sys.exit("usage: python -m chaser.agent <order id>")
    order_id = sys.argv[1] if len(sys.argv) == 2 else "(the order of the recorded run)"  # a Kitaru worker starts this with no order and supplies the recorded input
    # Built through Kitaru's factory path, not wrapped after the fact: only then can a replay answer the tools from a recording.
    runner = KitaruGraphRunner.from_agent_factory(create_agent, factory_kwargs={"model": ScriptedChaser(), "tools": [lookup_order, get_shipping_status], "system_prompt": PROMPT}, agent_id=None if os.environ.get("KITARU_TASK_ID") else uuid.UUID(AGENT_ID))
    state = asyncio.run(runner.ainvoke({"messages": [{"role": "user", "content": f"Chase order {order_id}."}]}))
    print(state["messages"][-1].content)


if __name__ == "__main__":
    main()
PYEOF
sed -i "s/AGENT_ID_HERE/$AID/" chaser/*.py
