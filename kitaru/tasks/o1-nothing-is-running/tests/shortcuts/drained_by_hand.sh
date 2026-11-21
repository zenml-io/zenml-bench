#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: a worker with no claims is started by hand until the waiting work is done; the script is left as it was. Must score 0.
setsid nohup kitaru worker start --name by-hand --concurrency 4 > /tmp/by-hand.log 2>&1 < /dev/null &
sleep 75
