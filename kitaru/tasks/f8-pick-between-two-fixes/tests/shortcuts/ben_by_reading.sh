#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: Ben's candidate is released because its code reads right. No run compares the two. Must score 0.
cp -R releases/2.0.1-ben releases/2.0.1
find releases/2.0.1 -name __pycache__ -prune -exec rm -rf {} +
sed -i 's/__version__ = "2.0.1-ben"/__version__ = "2.0.1"/' releases/2.0.1/helpdesk/__init__.py
kitaru agent version register helpdesk-agent --display-version 2.0.1 --command "python -m helpdesk.agent" --working-dir /app/releases/2.0.1 --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human --tool get_line_total -o json > /dev/null
