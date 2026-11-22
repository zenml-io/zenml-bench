#!/usr/bin/env bash
# Build one docker image per Kitaru task from kitaru/tasks/<task>/environment/Dockerfile, tagged the way the Prime
# taskset (integrations/prime/kitaru_bench) expects: zenmldocker/kitaru-bench-tasks:<task>-<version>. verifiers
# never builds Dockerfiles, so these must exist locally (docker runtime) or on the registry (Prime sandboxes).
#
#   kitaru/scripts/build_task_images.sh [task ...]          # default: every task
#   PLATFORM=linux/amd64 kitaru/scripts/build_task_images.sh  # for a push; the default is this machine's CPU type
set -euo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="${VERSION:-0.1.0}"
REPO="${REPO:-zenmldocker/kitaru-bench-tasks}"
if [ $# -gt 0 ]; then tasks=("$@"); else
  tasks=()
  for d in "$HERE"/kitaru/tasks/*/; do [ -f "$d/environment/Dockerfile" ] && tasks+=("$(basename "$d")"); done
fi
for t in "${tasks[@]}"; do
  tag="$REPO:$t-$VERSION"
  echo "== $tag"
  docker build -q ${PLATFORM:+--platform "$PLATFORM"} -t "$tag" "$HERE/kitaru/tasks/$t/environment" >/dev/null
done
