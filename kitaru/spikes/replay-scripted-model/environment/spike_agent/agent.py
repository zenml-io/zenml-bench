"""A PydanticAI agent whose "model" is a Python function, recorded by the real Kitaru adapter.

Run directly to record one session: `KITARU_AGENT_ID=<id> python -m spike_agent.agent "Refund order A-7"`.
A Kitaru worker runs the same command for a replay; the adapter then swaps in the recorded prompt.
"""
import asyncio
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from kitaru_pydantic_ai import KitaruAgent
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

LEDGER = Path(os.environ.get("SPIKE_LEDGER", "/app/ledger.jsonl"))


def scripted_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Decide the next step from the conversation so far: look up, maybe look up again, maybe refund, then answer."""
    requests = [m for m in messages if isinstance(m, ModelRequest)]
    returns = [p for m in requests for p in m.parts if isinstance(p, ToolReturnPart)]
    text = " ".join(str(getattr(p, "content", "")) for m in requests for p in m.parts if not isinstance(p, ToolReturnPart))
    order_id = re.search(r"[A-Z]-\d+", text).group()
    number = int(order_id.split("-")[1])
    lookups = [r for r in returns if r.tool_name == "lookup_order"]
    refunds = [r for r in returns if r.tool_name == "issue_refund"]
    call_id = f"call_{len(returns)}"
    if len(lookups) < (2 if number % 5 == 0 else 1):
        return ModelResponse(parts=[ToolCallPart("lookup_order", {"order_id": order_id}, tool_call_id=call_id)])
    order = lookups[-1].content
    if order["status"] == "delivered" and not refunds:
        return ModelResponse(parts=[ToolCallPart("issue_refund", {"order_id": order_id, "amount": order["amount"]}, tool_call_id=call_id)])
    if refunds:
        return ModelResponse(parts=[TextPart(f"Refunded {order['amount']} for {order_id}, receipt {refunds[-1].content['receipt']}, looked up at {order['served_at']}.")])
    return ModelResponse(parts=[TextPart(f"Order {order_id} was not found; nothing refunded.")])


def build_agent() -> Agent[None, str]:
    agent = Agent[None, str](FunctionModel(scripted_model), instructions="Resolve one refund request.")

    @agent.tool_plain
    def lookup_order(order_id: str) -> dict[str, Any]:
        """Look up an order. `served_at` changes on every live call, so a replay that shows the old value used the recording."""
        number = int(order_id.split("-")[1])
        return {"order_id": order_id, "status": "not_found" if number % 4 == 0 else "delivered", "amount": 10 + number, "served_at": time.time_ns()}

    @agent.tool_plain
    def issue_refund(order_id: str, amount: int) -> dict[str, Any]:
        """The side effect: append one row to the ledger file. A live call during a replay shows up as an extra row."""
        receipt = uuid.uuid4().hex[:12]
        with LEDGER.open("a") as f:
            f.write(json.dumps({"order_id": order_id, "amount": amount, "receipt": receipt, "replay": os.environ.get("KITARU_REPLAY_ID")}) + "\n")
        return {"receipt": receipt}

    return agent


async def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Refund order A-1"
    agent_id = os.environ.get("KITARU_AGENT_ID")
    agent = KitaruAgent(build_agent(), agent_id=uuid.UUID(agent_id) if agent_id else None, session_name=prompt)
    result = await agent.run(prompt)
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
