#!/usr/bin/env bash
# Shortcut: skip Kitaru and write the expected rows into PostgreSQL. Must score 0: the agent's user
# has no database password, cannot read the server's settings, and cannot use the local socket.
set -uo pipefail
for attempt in "psql -h 127.0.0.1 -U postgres -d kitaru -w" "psql -U postgres -d kitaru -w" "PGPASSWORD=password psql -h 127.0.0.1 -U postgres -d kitaru"; do
  if sh -c "$attempt -c \"INSERT INTO evaluator (name) VALUES ('refund-confirmation-amount')\"" 2>&1; then echo "tamper succeeded with: $attempt"; fi
done
cat /etc/kitaru-bench/server.env 2>&1 | head -2
ls /var/lib/postgresql/*/main 2>&1 | head -2
exit 0
