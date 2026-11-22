#!/usr/bin/env bash
# Starts Postgres, the Kitaru server and one worker if they are not running, then exits 0 only when
# all three answer. Safe to run again and again: Harbor calls it as the task's healthcheck.
set -u
LOG=/var/log/kitaru-bench; mkdir -p "$LOG"
mark() { [ -f "$LOG/$1" ] || date +%s.%N > "$LOG/$1"; }
mark t0_first_call
PGV=$(ls /usr/lib/postgresql)
pg_isready -q -h 127.0.0.1 || pg_ctlcluster "$PGV" main start >> "$LOG/postgres.log" 2>&1
pg_isready -q -h 127.0.0.1 || exit 1
mark t1_postgres
if ! pgrep -f "uvicorn kitaru.server" > /dev/null; then
  ( set -a; . /etc/kitaru-bench/server.env; set +a
    setsid nohup python -m uvicorn kitaru.server.api.main:app --factory --host 127.0.0.1 --port 8000 >> "$LOG/server.log" 2>&1 < /dev/null & )
fi
curl -fsS -m 3 http://127.0.0.1:8000/health/live > /dev/null 2>&1 || exit 1
mark t2_server
if ! pgrep -f "kitaru worker start" > /dev/null; then
  ( setsid nohup kitaru worker start --name bench-worker --concurrency 4 >> "$LOG/worker.log" 2>&1 < /dev/null & )
fi
kitaru worker list 2>> "$LOG/cli.log" | grep -q bench-worker || exit 1
mark t3_worker
