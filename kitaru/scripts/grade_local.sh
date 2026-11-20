#!/usr/bin/env bash
# Run one Kitaru task's grader locally in Docker, against a fresh container each time. For iterating
# on a grader, a reference or a shortcut before spending Modal time on the four checks.
#
#   kitaru/scripts/grade_local.sh kitaru/tasks/<task> [script.sh ...]     # no script = do nothing (the nop check)
#   BUILD=1 ...   rebuild the image first (needed after sync_env.sh)
#
# Each script runs as user `agent` in /app, the way an agent's commands do; then tests/test.sh runs
# as root. Prints reward and metrics per script.
set -uo pipefail
TASK=${1:?usage: grade_local.sh kitaru/tasks/<task> [script.sh ...]}; shift
IMAGE="kitaru-local/$(basename "$TASK")"
if [ "${BUILD:-0}" = 1 ] || ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
  docker build -q -t "$IMAGE" "$TASK/environment" > /dev/null || { echo "image build failed" >&2; exit 1; }
fi
[ $# -gt 0 ] || set -- ""
for SCRIPT in "$@"; do
  C="kitaru-grade-$$-$RANDOM"
  docker run -d --name "$C" "$IMAGE" sleep infinity > /dev/null
  for i in $(seq 40); do docker exec "$C" /opt/kitaru-bench/start.sh && break; sleep 2; done
  docker cp "$TASK/tests" "$C:/tests" > /dev/null
  if [ -n "$SCRIPT" ]; then
    docker exec "$C" mkdir -p /solution && docker cp "$SCRIPT" "$C:/solution/solve.sh" > /dev/null
    docker cp "$TASK/solution/solve.sh" "$C:/solution/reference.sh" > /dev/null
    docker exec "$C" chmod -R a+rx /solution
    docker exec -u agent -w /app -e HOME=/home/agent "$C" bash /solution/solve.sh > "/tmp/$C.agent.log" 2>&1 || echo "  (script exited $?)"
  fi
  docker exec "$C" bash /tests/test.sh
  echo "== ${SCRIPT:-<nothing>}: reward $(docker exec "$C" cat /logs/verifier/reward.txt)"
  docker exec "$C" cat /logs/verifier/metrics.json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  ", {k: v for k, v in d.items() if k not in ("false_alarms","missed")}); print("   false alarms:", d.get("false_alarms")); print("   missed:", d.get("missed"))' 2>/dev/null
  [ "${KEEP:-0}" = 1 ] && echo "   kept container $C (agent log /tmp/$C.agent.log)" || docker rm -f "$C" > /dev/null
done
