#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: the planner sends everything that is ready in one response, and the tools themselves let four requests to the order service run at a time.
cp -R releases/2.0.0 releases/2.0.1
find releases/2.0.1 -name __pycache__ -prune -exec rm -rf {} +
sed -i 's/__version__ = "2.0.0"/__version__ = "2.0.1"/' releases/2.0.1/helpdesk/__init__.py
python3 - <<'PY'
from pathlib import Path
p = Path("releases/2.0.1/helpdesk/planner.py"); s = p.read_text()
def cut(old, new=""):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
cut("""    return ModelResponse(parts=[ToolCallPart(step[0], step[1], tool_call_id=f"call_{len(returns)}")])
""", """    calls = step if isinstance(step, list) else [step]  # the tool calls of one response run at the same time
    return ModelResponse(parts=[ToolCallPart(tool, args, tool_call_id=f"call_{len(returns)}_{i}") for i, (tool, args) in enumerate(calls[:AT_ONCE])])
""")
cut("Call = tuple[str, dict[str, Any]]\n", "Call = tuple[str, dict[str, Any]]\nAT_ONCE = 99  # the order service serves four requests at a time\n")
cut("def _status(order_ids: list[str], got: Callable[..., list[dict[str, Any]]], careful: bool) -> Call | str:", "def _status_one(order_ids: list[str], got: Callable[..., list[dict[str, Any]]], careful: bool) -> Call | str:")
cut('step = _status(order_ids, got, careful) if kind == "status"', 'step = _status_all(order_ids, got, careful) if kind == "status"')
s += """

def _status_all(order_ids: list[str], got: Callable[..., list[dict[str, Any]]], careful: bool) -> list[Call] | str:
    \"\"\"The next call for every order that needs one, or the answer once none does. Orders do not depend on each other.\"\"\"
    steps = [_status_one([order_id], got, careful) for order_id in order_ids]
    return [s for s in steps if isinstance(s, tuple)] or " ".join(steps)
"""
cut("""    order = _read_order(order_id, got)
    if order is None:
        return f"I could not find order {order_id}. Please check the number."
    if isinstance(order, tuple):
        return order
    email = account.group() if account else order["customer_email"] if careful else None
""", """    if account and not got("lookup_order", order_id=order_id) and not got("lookup_customer"):
        return [("lookup_order", {"order_id": order_id}), ("lookup_customer", {"email": account.group()})]  # neither needs the other's answer
    order = _read_order(order_id, got)
    if order is None:
        return f"I could not find order {order_id}. Please check the number."
    if isinstance(order, tuple):
        return order
    email = account.group() if account else order["customer_email"] if careful else None
""")
cut("""def _dispute(order_id: str, account: re.Match | None, got: Callable[..., list[dict[str, Any]]], careful: bool) -> Call | str:
""", """def _dispute(order_id: str, account: re.Match | None, got: Callable[..., list[dict[str, Any]]], careful: bool) -> Call | list[Call] | str:
    if careful and account and not got("lookup_order", order_id=order_id) and not got("lookup_customer"):
        return [("lookup_order", {"order_id": order_id}), ("lookup_customer", {"email": account.group()})]  # neither needs the other's answer
""")
p.write_text(s)
PY
kitaru agent version register helpdesk-agent --display-version 2.0.1 --command "python -m helpdesk.agent" --working-dir /app/releases/2.0.1 --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
python3 - <<'PY'
from pathlib import Path
p = Path("releases/2.0.1/helpdesk/tools.py"); s = p.read_text()
def cut(old, new=""):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
cut("import json\n", "import json\nimport threading\n")
cut('FINANCE = os.environ.get("HELPDESK_FINANCE_URL", "http://127.0.0.1:8091")\n', 'FINANCE = os.environ.get("HELPDESK_FINANCE_URL", "http://127.0.0.1:8091")\n_slots = threading.BoundedSemaphore(4)  # the order service serves four requests at a time\n')
cut("""    try:
        return json.loads(urllib.request.urlopen(ORDERS + path, timeout=20).read())
""", """    try:
        with _slots:
            return json.loads(urllib.request.urlopen(ORDERS + path, timeout=20).read())
""")
p.write_text(s)
PY
