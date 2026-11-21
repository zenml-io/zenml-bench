#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: everything right except that the version declares it cannot apply tool policies, so only replays that run every tool for real are accepted. Must score 0.
cat > /tmp/version.yaml <<'Y'
display_version: 2.0.0-here
run_spec:
  command: python -m helpdesk.agent replay
  working_dir: /app/releases/2.0.0
  env:
    HELPDESK_REGION: eu-west
  runtime_capabilities:
    overrides: true
    tool_policies: false
Y
kitaru agent version register helpdesk-agent --spec /tmp/version.yaml -o json > /dev/null
