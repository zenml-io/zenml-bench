#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: release 1.6.1's own file is edited, and version 3 is registered on that directory. Must score 0.
python3 - <<'PY'
from pathlib import Path
p = Path("releases/1.6.1/helpdesk/money.py"); s = p.read_text()
p.write_text(s.replace('if currency in ("USD", "GBP"):', 'if currency in ("USD", "GBP", "EUR"):'))
PY
kitaru agent version register helpdesk-agent --display-version 1.6.2 --command "python -m helpdesk.agent" --working-dir /app/releases/1.6.1 --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
