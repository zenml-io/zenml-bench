"""The parcel chaser: looks at one order that has not arrived and writes the note the customer gets. A LangGraph agent.

    python -m chaser.agent SO-20016
"""
import sys

from langchain.agents import create_agent

from .model import ScriptedChaser
from .tools import get_shipping_status, lookup_order

PROMPT = "You chase late parcels for Larkspur Goods. Write the customer one short note."


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m chaser.agent <order id>")
    graph = create_agent(model=ScriptedChaser(), tools=[lookup_order, get_shipping_status], system_prompt=PROMPT)
    state = None
    for state in graph.stream({"messages": [{"role": "user", "content": f"Chase order {sys.argv[1]}."}]}, stream_mode="values"):
        print(f"[{len(state['messages'])} messages]", file=sys.stderr)  # progress, for whoever watches the run
    print(state["messages"][-1].content)


if __name__ == "__main__":
    main()
