#!/usr/bin/env bash
# Starts PostgreSQL, the Kitaru server and one worker if they are not running, then exits 0 only
# when all three answer. Safe to run again and again: Harbor calls it as the task's healthcheck,
# image builds call it to load a world, and the grader calls it before grading.
#
#   start.sh            everything; the worker runs as user `agent`
#   start.sh --no-worker   Postgres and the server only
set -u
[ "$(id -u)" = 0 ] || { echo "start.sh must run as root" >&2; exit 2; }
WORKER=1; [ "${1:-}" = "--no-worker" ] && WORKER=0
LOG=/var/log/kitaru-bench; ENVF=/etc/kitaru-bench/server.env
mkdir -p "$LOG" /etc/kitaru-bench; chmod 755 "$LOG"
mark() { [ -f "$LOG/$1" ] || date +%s.%N > "$LOG/$1"; }
mark t0_first_call
PGV=$(ls /usr/lib/postgresql)
pg_isready -q -h 127.0.0.1 || pg_ctlcluster "$PGV" main start >> "$LOG/postgres.log" 2>&1
pg_isready -q -h 127.0.0.1 || exit 1
mark t1_postgres
if ! pgrep -f "uvicorn kitaru.server" > /dev/null; then
  # A new database password and new server keys every time the server starts, kept in a file only
  # root can read. The agent reaches Kitaru over HTTP and never learns them.
  PW=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')
  su postgres -c "psql -q -c \"ALTER USER postgres PASSWORD '$PW'\"" >> "$LOG/postgres.log" 2>&1 || exit 1
  key() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9'; }
  [ -f /etc/kitaru-bench/keys.env ] || { umask 077; printf 'KITARU_SERVER_SECRET_ENCRYPTION_KEY=%s\nKITARU_SERVER_JWT_SIGNING_KEY=%s\n' "$(key)" "$(key)" > /etc/kitaru-bench/keys.env; }
  ( umask 077; { echo KITARU_SERVER_AUTH_SCHEME=none; echo KITARU_SERVER_DB_HOST=127.0.0.1; echo KITARU_SERVER_DB_PORT=5432
      echo KITARU_SERVER_DB_NAME=kitaru; echo "KITARU_SERVER_DB_PWD=$PW"; echo KITARU_SERVER_ANALYTICS_OPT_IN=false; cat /etc/kitaru-bench/keys.env; } > "$ENVF" )
  ( set -a; . "$ENVF"; set +a; cd /
    setsid nohup python -m uvicorn kitaru.server.api.main:app --factory --host 127.0.0.1 --port 8000 >> "$LOG/server.log" 2>&1 < /dev/null & )
fi
curl -fsS -m 3 http://127.0.0.1:8000/health/live > /dev/null 2>&1 || exit 1
mark t2_server
[ "$WORKER" = 1 ] || exit 0
if ! pgrep -f "kitaru worker start" > /dev/null; then
  touch "$LOG/worker.log"; chown agent "$LOG/worker.log"
  ( cd /app && setsid nohup runuser -u agent -- kitaru worker start --name "${WORKER_NAME:-bench-worker}" --concurrency 4 >> "$LOG/worker.log" 2>&1 < /dev/null & )
fi
kitaru worker list 2> /dev/null | grep -q '"status":"live"' || exit 1
mark t3_worker
