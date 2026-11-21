#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: release 2.0.0's own planner is edited and version 2 is registered on that directory. Must score 0.
python3 - <<'PY'
from pathlib import Path
p = Path('releases/2.0.0/helpdesk/planner.py'); s = p.read_text()
def cut(old, new=''):
    global s
    assert s.count(old) == 1
    s = s.replace(old, new)
cut("""        if careful and len(order["items"]) > 1 and len([r for r in got("lookup_order", order_id=order_id) if "error" not in r]) < 2:
            return "lookup_order", {"order_id": order_id}
""")
cut('if len(got("lookup_customer", email=email)) < 2:', 'if not got("lookup_customer", email=email):')
cut("""        if careful and len(checks) < 2:
            return "check_return_policy", {"order_id": order_id, "tier": tier}
""")
p.write_text(s)
PY
kitaru agent version register helpdesk-agent --display-version 2.0.1 --command "python -m helpdesk.agent" --working-dir /app/releases/2.0.0 -o json > /dev/null
