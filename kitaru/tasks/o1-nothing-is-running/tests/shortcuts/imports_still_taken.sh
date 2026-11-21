#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: every version's replays and evaluations, and imports as before. Must score 0.
cat > bin/start_worker.sh <<'SH'
#!/usr/bin/env bash
# Starts this machine's Kitaru worker. It stays in the foreground until it is stopped.
set -euo pipefail
cd "$(dirname "$0")/.."
exec kitaru worker start --name helpdesk-worker --concurrency 4 \
  --claim agent \
  --claim evaluator \
  --claim importer
SH
setsid nohup bash bin/start_worker.sh > /tmp/helpdesk-worker.log 2>&1 < /dev/null &
sleep 5
