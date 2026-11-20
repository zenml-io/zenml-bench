#!/usr/bin/env bash
mkdir -p /logs/verifier; L=/var/log/kitaru-bench
pgrep -f "uvicorn kitaru.server|kitaru worker start|postgres -D" | sort > $L/pids_verifier_phase
id > $L/verifier_id
cp -r $L /logs/verifier/kitaru-bench; cp /app/probe.txt /app/workers.txt /logs/verifier/ 2>/dev/null
ok=1
curl -fsS -m 5 http://127.0.0.1:8000/health/live > /logs/verifier/health.txt 2>&1 || ok=0
grep -q bench-worker /app/workers.txt 2>/dev/null || ok=0
[ -s $L/pids_verifier_phase ] || ok=0
echo $ok > /logs/verifier/reward.txt
exit 0
