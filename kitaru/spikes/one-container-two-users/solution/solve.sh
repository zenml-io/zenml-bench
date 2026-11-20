#!/usr/bin/env bash
kitaru worker list > /app/workers.txt 2>&1
P=/app/probe.txt
try() { echo "## $*" >> $P; ( eval "$@" ) >> $P 2>&1; echo "-> exit $?" >> $P; }
try id
try "cat /etc/kitaru-bench/server.env | head -2"
try "PGPASSWORD=password psql -h 127.0.0.1 -U postgres -d kitaru -c 'select 1' | head -3"
try "psql -h 127.0.0.1 -U postgres -d kitaru -w -c 'select 1' | head -3"
try "psql -U postgres -d kitaru -w -c 'select 1' | head -3"
try "ls /var/lib/postgresql/*/main | head -3"
try "tr '\\0' '\\n' < /proc/\$(pgrep -f 'uvicorn kitaru.server' | head -1)/environ | grep -c KITARU_SERVER"
try "pkill -f 'kitaru worker start'; sleep 1; pgrep -f 'kitaru worker start' | wc -l"
try "sudo -n true"
try "su postgres -c 'psql -c \"select 1\"' < /dev/null | head -3"
try "cat /var/log/kitaru-bench/server.log | head -2"
try "kitaru session list | head -c 200"
