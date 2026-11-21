#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Another valid route: the claims are set through the worker's environment variable, and the worker also takes analyzer work, which the README does not rule out.
cat > bin/start_worker.sh <<'SH'
#!/usr/bin/env bash
# Starts this machine's Kitaru worker. It stays in the foreground until it is stopped.
set -euo pipefail
cd "$(dirname "$0")/.."
export KITARU_WORKER_SCOPE__CLAIMS='[{"kind":"agent"},{"kind":"evaluator"},{"kind":"analyzer"}]'
exec kitaru worker start --name helpdesk-worker --concurrency 4
SH
setsid nohup bash bin/start_worker.sh > /tmp/helpdesk-worker.log 2>&1 < /dev/null &
sleep 5
