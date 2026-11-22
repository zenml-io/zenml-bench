#!/usr/bin/env bash
# Build a task's environment/ directory from the shared parts. Harbor (and Modal) build from that
# directory alone, so everything the image needs is copied into it:
#
#   environment/Dockerfile   = FROM <the published base image, pinned by digest: base/IMAGE>
#                              + worlds/<world>/Dockerfile.world + tasks/<task>/Dockerfile.task
#   environment/world/       = the world's loader and its session files (generated here from story.py)
#   environment/workspace/   = the world's workspace (what the agent sees in /app), with tasks/<task>/workspace/ laid over it if present
#   environment/setup/       = tasks/<task>/setup/ if present, for the task's Dockerfile.task
#   tests/fixtures/ground_truth.json = the world's answer key, for the grader only
#
# The world is named in tasks/<task>/world; tasks/<task>/plants, if present, is passed to the world's story as --plants. Run from the repo root after editing base/ or a world:
#   kitaru/scripts/sync_env.sh kitaru/tasks/<task>
# Never edit a task's environment/ by hand.
set -euo pipefail
TASK=${1:?usage: sync_env.sh kitaru/tasks/<task>}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORLD=$(tr -d '[:space:]' < "$TASK/world")
ENV="$TASK/environment"
rm -rf "$ENV"; mkdir -p "$ENV/world"
cp -R "$ROOT/worlds/$WORLD/workspace" "$ENV/workspace"
# tasks/<task>/workspace (optional): files laid over the world's workspace for this task only.
if [ -d "$TASK/workspace" ]; then cp -R "$TASK/workspace/." "$ENV/workspace/"; fi
# tasks/<task>/setup (optional): files the task's Dockerfile.task copies in to prepare Kitaru's state while the image is built.
if [ -d "$TASK/setup" ]; then cp -R "$TASK/setup" "$ENV/setup"; fi
cp "$ROOT/worlds/$WORLD/load.py" "$ENV/world/"
if [ -d "$ROOT/worlds/$WORLD/old" ]; then cp -R "$ROOT/worlds/$WORLD/old" "$ENV/world/old"; fi
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
# tasks/<task>/plants (optional) names an extra set of planted problems for this task's copy of the world.
PLANTS=(); if [ -f "$TASK/plants" ]; then PLANTS=(--plants "$(tr -d '[:space:]' < "$TASK/plants")"); fi
python3 "$ROOT/worlds/$WORLD/story.py" history ${PLANTS[@]+"${PLANTS[@]}"} --out "$TMP" > /dev/null
mkdir -p "$TASK/tests/fixtures"
if [ -f "$TMP/reviewed.json" ]; then cp "$TMP/reviewed.json" "$ENV/world/reviewed.json"; fi   # verdicts the agent can see in Kitaru anyway
if [ -f "$TMP/services_data.json" ]; then cp "$TMP/services_data.json" "$ENV/world/services_data.json"; fi   # what a world's own services read; root-only in the image
cp "$TMP/ground_truth.json" "$TASK/tests/fixtures/ground_truth.json"   # the answer key goes to tests/ only, never into the image
python3 - "$TMP" "$ENV/world" <<'PY'
import gzip, json, pathlib, sys
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
for f in sorted(src.glob("sessions-*.jsonl")):
    with gzip.GzipFile(dst / (f.name + ".gz"), "wb", mtime=0) as out:  # mtime=0: the same story gives the same bytes
        out.write(f.read_bytes())
truth = json.loads((src / "ground_truth.json").read_text())
(dst / "plan.json").write_text(json.dumps({"sessions": truth["sessions"], "by_version": truth["by_version"]}))  # counts only; the answer key stays out of the image
PY
# The base image is published and pinned by digest, so a task build pulls it and adds only the world.
# base/Dockerfile is what that image was built from (kitaru/README.md, "Publishing the base image").
{ echo "FROM $(tr -d '[:space:]' < "$ROOT/base/IMAGE")"; cat "$ROOT/worlds/$WORLD/Dockerfile.world"; [ -f "$TASK/Dockerfile.task" ] && cat "$TASK/Dockerfile.task"; true; } > "$ENV/Dockerfile"
du -sh "$ENV" | cut -f1
