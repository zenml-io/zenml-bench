#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Reference: the script's explicit claims replace the defaults. It claimed one agent version and imports, so evaluations were never taken, replays against any other version never will be,
# and imports would be. The worker now claims agent work for every version and evaluations, and nothing else.
cat > bin/start_worker.sh <<'SH'
#!/usr/bin/env bash
# Starts this machine's Kitaru worker. It stays in the foreground until it is stopped.
set -euo pipefail
cd "$(dirname "$0")/.."
exec kitaru worker start --name helpdesk-worker --concurrency 4 \
  --claim agent \
  --claim evaluator
SH
setsid nohup bash bin/start_worker.sh > /tmp/helpdesk-worker.log 2>&1 < /dev/null &
sleep 5
