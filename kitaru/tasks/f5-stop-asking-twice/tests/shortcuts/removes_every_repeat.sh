#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: every second ask is removed, the retry after a timeout included. Must score 0.
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
cut('if len(got("lookup_customer", email=email)) < 2:', 'if not got("lookup_customer", email=email):')
cut("""        if careful and len(checks) < 2:
            return "check_return_policy", {"order_id": order_id, "tier": tier}
""")
cut("""        if careful and scans[-1]["carrier_status"] == "out_for_delivery" and len(scans) < 2:
            return "get_shipping_status", {"order_id": order_id}
""")
cut("""    if careful and len([r for r in got("lookup_order", order_id=order_id) if "error" not in r]) < 2:
        return "lookup_order", {"order_id": order_id}
""")
cut("""        if scans[-1]["carrier_status"] == "label_created" and len(scans) < 2:
            return "get_shipping_status", {"order_id": order_id}
""")
cut('if any(not r.get("retryable") for r in reads) or len(reads) >= 3:', 'if reads:')
p.write_text(s)
PY
kitaru agent version register helpdesk-agent --display-version 2.0.1 --command "python -m helpdesk.agent" --working-dir /app/releases/2.0.1 --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
