#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: evaluations in, imports out, and replays still only for the one version the script named. Must score 0.
V1=$(kitaru agent version get helpdesk-agent@1 -o json | python3 -c 'import sys, json; print(json.load(sys.stdin)["item"]["id"])')
cat > bin/start_worker.sh <<SH
#!/usr/bin/env bash
# Starts this machine's Kitaru worker. It stays in the foreground until it is stopped.
set -euo pipefail
cd /app
exec kitaru worker start --name helpdesk-worker --concurrency 4 \
  --claim agent=$V1 \
  --claim evaluator
SH
setsid nohup bash bin/start_worker.sh > /tmp/helpdesk-worker.log 2>&1 < /dev/null &
sleep 5
