"""The parcel chaser: looks at one order that has not arrived and writes the note the customer gets.

    python -m chaser.agent SO-20016
"""
import sys

from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel

from .planner import next_step
from .tools import get_shipping_status, lookup_order


def build_agent() -> Agent[None, str]:
    agent = Agent[None, str](FunctionModel(next_step), instructions="You chase late parcels for Larkspur Goods. Write the customer one short note.")
    agent.tool_plain(lookup_order)
    agent.tool_plain(get_shipping_status)
    return agent


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m chaser.agent <order id>")
    result = build_agent().run_sync(f"Chase order {sys.argv[1]}.")
    print(result.output)


if __name__ == "__main__":
    main()
