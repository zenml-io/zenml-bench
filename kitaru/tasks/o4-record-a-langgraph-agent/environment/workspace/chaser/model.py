"""What the parcel chaser does next. In production a hosted chat model decides; here the same decisions are written
out as a LangChain chat model, so an order gives the same run every time."""
import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedChaser(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "scripted-chaser"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChaser":
        return self

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        text = " ".join(str(m.content) for m in messages if m.type == "human")
        order_id = re.search(r"SO-\d{5}", text).group()
        returns = [(m.name, json.loads(m.content) if isinstance(m.content, str) else m.content) for m in messages if isinstance(m, ToolMessage)]
        call = lambda tool: AIMessage(content="", tool_calls=[{"name": tool, "args": {"order_id": order_id}, "id": f"call_{len(returns)}", "type": "tool_call"}])
        reads = [r for name, r in returns if name == "lookup_order"]
        orders = [r for r in reads if "error" not in r]
        if not orders:
            if len(reads) >= 2 or any(not r.get("retryable") for r in reads):
                return AIMessage(content=f"Order {order_id} could not be read; nothing was sent.")
            return call("lookup_order")
        order = orders[-1]
        if order["status"] != "shipped":
            return AIMessage(content=f"Order {order_id} is {order['status']}; there is no parcel to chase.")
        scans = [r for name, r in returns if name == "get_shipping_status"]
        if not scans or scans[-1]["carrier_status"] == "label_created" and len(scans) < 2:
            return call("get_shipping_status")
        where = scans[-1]["carrier_status"].replace("_", " ")
        return AIMessage(content=f"Note to {order['customer_email']}: your order {order_id} is {where}; the carrier's last scan was at {scans[-1]['last_scan'] or 'no scan yet'}.")
