#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the factory construction, still read with stream(), which the adapter refuses before the graph runs. Must score 0.
AID=$(kitaru agent register parcel-chaser --description "Chases late parcels: one note per order." --display-version 1.0.0 --command "python -m chaser.agent replay" --working-dir /app --tool lookup_order --tool get_shipping_status -o json | python3 -c 'import sys, json; print(json.load(sys.stdin)["item"]["agent"]["id"])')
cat > chaser/agent.py <<'PYEOF'
"""The parcel chaser: looks at one order that has not arrived and writes the note the customer gets. A LangGraph agent.

    python -m chaser.agent SO-20016
"""
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
    if len(sys.argv) != 2:
        sys.exit("usage: python -m chaser.agent <order id>")
    runner = KitaruGraphRunner.from_agent_factory(create_agent, factory_kwargs={"model": ScriptedChaser(), "tools": [lookup_order, get_shipping_status], "system_prompt": PROMPT}, agent_id=None if os.environ.get("KITARU_TASK_ID") else uuid.UUID(AGENT_ID))
    state = None
    for state in runner.stream({"messages": [{"role": "user", "content": f"Chase order {sys.argv[1]}."}]}, stream_mode="values"):
        print(f"[{len(state['messages'])} messages]", file=sys.stderr)
    print(state["messages"][-1].content)


if __name__ == "__main__":
    main()
PYEOF
sed -i "s/AGENT_ID_HERE/$AID/" chaser/*.py
