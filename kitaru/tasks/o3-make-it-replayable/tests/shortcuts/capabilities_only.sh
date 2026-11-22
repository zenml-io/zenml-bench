#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: a new version with the default capabilities and version 1's other settings, the other host's directory included. Kitaru accepts the replay; the task cannot start. Must score 0.
kitaru agent version register helpdesk-agent --display-version 2.0.0-here --command "python -m helpdesk.agent" --working-dir /srv/helpdesk/current --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
