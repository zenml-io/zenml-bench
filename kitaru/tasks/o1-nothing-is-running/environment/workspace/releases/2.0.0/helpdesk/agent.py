"""The helpdesk assistant: a PydanticAI agent recorded in Kitaru.

    KITARU_AGENT_ID=<id> python -m helpdesk.agent "Where is order SO-20001? My account is maya.1@example.org."

A Kitaru worker runs the same command to replay a recorded conversation; the adapter then supplies the recorded message."""
import asyncio
import os
import sys
import uuid

from kitaru_pydantic_ai import KitaruAgent
from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel

from . import tools
from .planner import next_step

EFFORT = "high"  # the reasoning effort production runs at


def build_agent() -> Agent[None, str]:
    agent = Agent[None, str](FunctionModel(next_step), instructions="You are the helpdesk assistant for Larkspur Goods. Resolve one customer message.")
    for tool in tools.ALL:
        agent.tool_plain(tool)
    return agent


async def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Where is order SO-20001? My account is maya.1@example.org."
    ids = {name: uuid.UUID(os.environ[var]) if os.environ.get(var) else None for name, var in (("agent_id", "KITARU_AGENT_ID"), ("agent_version_id", "KITARU_AGENT_VERSION_ID"))}
    result = await KitaruAgent(build_agent(), **ids).run(prompt, model_settings={"reasoning_effort": EFFORT})
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
