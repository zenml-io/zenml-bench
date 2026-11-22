#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: capabilities and directory are right; the entrypoint still exits because the worker gives it no message. Must score 0.
kitaru agent version register helpdesk-agent --display-version 2.0.0-here --command "python -m helpdesk.agent" --working-dir /app/releases/2.0.0 --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
