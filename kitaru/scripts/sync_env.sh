#!/usr/bin/env bash
# Build a task's environment/ directory from the shared parts. Harbor (and Modal) build from that
# directory alone, so everything the image needs is copied into it:
#
#   environment/Dockerfile   = base/Dockerfile + worlds/<world>/Dockerfile.world + tasks/<task>/Dockerfile.task
#   environment/base/files/  = base/files/
#   environment/world/       = the world's loader and its session files (generated here from story.py)
#   environment/workspace/   = the world's workspace (what the agent sees in /app)
#   tests/fixtures/ground_truth.json = the world's answer key, for the grader only
#
# The world is named in tasks/<task>/world. Run from the repo root after editing base/ or a world:
#   kitaru/scripts/sync_env.sh kitaru/tasks/<task>
# Never edit a task's environment/ by hand.
set -euo pipefail
TASK=${1:?usage: sync_env.sh kitaru/tasks/<task>}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORLD=$(tr -d '[:space:]' < "$TASK/world")
ENV="$TASK/environment"
rm -rf "$ENV"; mkdir -p "$ENV/base" "$ENV/world"
cp -R "$ROOT/base/files" "$ENV/base/files"
cp -R "$ROOT/worlds/$WORLD/workspace" "$ENV/workspace"
cp "$ROOT/worlds/$WORLD/load.py" "$ENV/world/"
if [ -d "$ROOT/worlds/$WORLD/old" ]; then cp -R "$ROOT/worlds/$WORLD/old" "$ENV/world/old"; fi
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
python3 "$ROOT/worlds/$WORLD/story.py" history --out "$TMP" > /dev/null
mkdir -p "$TASK/tests/fixtures"
if [ -f "$TMP/reviewed.json" ]; then cp "$TMP/reviewed.json" "$ENV/world/reviewed.json"; fi   # verdicts the agent can see in Kitaru anyway
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
{ cat "$ROOT/base/Dockerfile" "$ROOT/worlds/$WORLD/Dockerfile.world"; [ -f "$TASK/Dockerfile.task" ] && cat "$TASK/Dockerfile.task"; true; } > "$ENV/Dockerfile"
du -sh "$ENV" | cut -f1
