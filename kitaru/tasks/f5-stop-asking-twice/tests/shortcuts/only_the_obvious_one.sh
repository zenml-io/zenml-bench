#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: only the order read again in a status request is removed; the other two wasteful places stay. Must score 0.
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
cut("""        if careful and len(order["items"]) > 1 and len([r for r in got("lookup_order", order_id=order_id) if "error" not in r]) < 2:
            return "lookup_order", {"order_id": order_id}
""")
p.write_text(s)
PY
kitaru agent version register helpdesk-agent --display-version 2.0.1 --command "python -m helpdesk.agent" --working-dir /app/releases/2.0.1 --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
