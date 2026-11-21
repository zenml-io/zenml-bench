"""The nightly run of the parcel chaser: one note per order in a file of order ids, one id per line.

    python -m chaser.nightly /path/to/orders.txt
"""
import asyncio
import sys
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel

from .planner import next_step
from .tools import get_shipping_status, lookup_order

chaser = Agent[None, str](FunctionModel(next_step), instructions="You chase late parcels for Larkspur Goods. Write the customer one short note.", tools=[lookup_order, get_shipping_status])


async def chase_all(order_ids: list[str]) -> list[str]:
    notes = []
    for order_id in order_ids:  # one at a time: the order service serves few requests at once
        notes.append((await chaser.run(f"Chase order {order_id}.")).output)
    return notes


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m chaser.nightly <file of order ids>")
    order_ids = [line.strip() for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
    for note in asyncio.run(chase_all(order_ids)):
        print(note)


if __name__ == "__main__":
    main()
