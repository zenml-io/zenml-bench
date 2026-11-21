#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Reference: version 1 declares that it can apply neither overrides nor tool policies, and runs from a directory of another host. A new version is registered with the defaults for both,
# this machine's directory, the region the team's script sets, and a placeholder message in the command, because the entrypoint refuses to start without one (under a replay the adapter supplies the recorded message).
kitaru agent version register helpdesk-agent --display-version 2.0.0-here --command "python -m helpdesk.agent replay" --working-dir /app/releases/2.0.0 --env HELPDESK_REGION=eu-west --tool lookup_order --tool lookup_customer --tool check_return_policy --tool get_shipping_status --tool issue_refund --tool escalate_to_human -o json > /dev/null
