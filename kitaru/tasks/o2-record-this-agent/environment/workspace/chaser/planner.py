"""What the parcel chaser does next. In production a hosted model decides; here the same decisions are a function,
so an order gives the same run every time."""
import re

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo


def next_step(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    requests = [m for m in messages if isinstance(m, ModelRequest)]
    returns = [p for m in requests for p in m.parts if isinstance(p, ToolReturnPart)]
    text = " ".join(str(getattr(p, "content", "")) for m in requests for p in m.parts if not isinstance(p, ToolReturnPart))
    order_id = re.search(r"SO-\d{5}", text).group()
    call = lambda tool: ModelResponse(parts=[ToolCallPart(tool, {"order_id": order_id}, tool_call_id=f"call_{len(returns)}")])
    say = lambda note: ModelResponse(parts=[TextPart(note)])
    reads = [r.content for r in returns if r.tool_name == "lookup_order"]
    orders = [r for r in reads if "error" not in r]
    if not orders:
        if len(reads) >= 2 or any(not r.get("retryable") for r in reads):
            return say(f"Order {order_id} could not be read; nothing was sent.")
        return call("lookup_order")
    order = orders[-1]
    if order["status"] != "shipped":
        return say(f"Order {order_id} is {order['status']}; there is no parcel to chase.")
    scans = [r.content for r in returns if r.tool_name == "get_shipping_status"]
    if not scans or scans[-1]["carrier_status"] == "label_created" and len(scans) < 2:
        return call("get_shipping_status")
    where = scans[-1]["carrier_status"].replace("_", " ")
    return say(f"Note to {order['customer_email']}: your order {order_id} is {where}; the carrier's last scan was at {scans[-1]['last_scan'] or 'no scan yet'}.")
