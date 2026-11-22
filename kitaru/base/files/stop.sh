#!/usr/bin/env bash
# Stops the worker, the server and PostgreSQL cleanly. Used at the end of an image build, so the
# database files in the image are consistent. `stop.sh --workers` stops only the workers.
# (The process names live in this file and in start.sh only. A Dockerfile RUN line that spelled them
# out would itself match start.sh's `pgrep -f`, and start.sh would think the server was already up.)
set -u
pkill -f "kitaru worker start" || true
[ "${1:-}" = "--workers" ] && exit 0
pkill -f "uvicorn kitaru.server" || true
sleep 2
pg_ctlcluster "$(ls /usr/lib/postgresql)" main stop -- -m fast
