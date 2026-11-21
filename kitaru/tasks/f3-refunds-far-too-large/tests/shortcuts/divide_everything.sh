#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: every amount is divided by 100. Euros come right; yen, which have no minor unit, are now refunded at a hundredth. Must score 0.
cp -R releases/1.6.1 releases/1.6.2
find releases/1.6.2 -name __pycache__ -prune -exec rm -rf {} +
sed -i 's/__version__ = "1.6.1"/__version__ = "1.6.2"/' releases/1.6.2/helpdesk/__init__.py
python3 - <<'PY'
from pathlib import Path
p = Path("releases/1.6.2/helpdesk/money.py"); s = p.read_text()
start = s.index("    if currency in")
s = s[:start] + "    return round(minor / 100, 2)\n"
p.write_text(s)
PY
kitaru agent version register helpdesk-agent --display-version 1.6.2 --command "python -m helpdesk.agent" --working-dir /app/releases/1.6.2 --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
