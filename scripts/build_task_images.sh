#!/usr/bin/env bash
# Build one docker image per task from tasks/<task>/environment/Dockerfile, tagged the way the Prime taskset
# (integrations/prime/zenml_bench) expects: zenml-bench/<task>:<version>. verifiers never builds Dockerfiles, so these
# must exist before `eval zenml-bench` runs on the docker runtime. Requires the base image (docker build -t
# zenml-bench/base:0.96.4 shared/base) and OrbStack (docker context use orbstack).
#
#   scripts/build_task_images.sh [task ...]          # default: every tasks/*/ with an environment/Dockerfile
#   VERSION=0.1.0 PREFIX=zenml-bench scripts/build_task_images.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-0.1.0}"
PREFIX="${PREFIX:-zenml-bench}"
if [ $# -gt 0 ]; then tasks=("$@"); else
  tasks=()
  for d in "$HERE"/tasks/*/; do [ -f "$d/environment/Dockerfile" ] && tasks+=("$(basename "$d")"); done
fi
for t in "${tasks[@]}"; do
  tag="$PREFIX/$t:$VERSION"
  echo "== $tag"
  docker build -q -t "$tag" "$HERE/tasks/$t/environment" >/dev/null
done
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep "^$PREFIX/" | sort
