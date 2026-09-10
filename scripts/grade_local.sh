#!/usr/bin/env bash
# usage: scripts/grade_local.sh <task-dir> [patch-script]
# Copies the task's project (shared/projects/<name>, where <name> is the dir synced under environment/) to a temp dir, applies the patch (a solution or shortcut), grades it in a
# fresh ZenML store with the task's own tests, and prints the reward. No Docker, no Harbor.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK="$1"; PATCH="${2:-}"
PROJECT="$(for d in "$ROOT/$TASK"/environment/*/; do n="$(basename "$d")"; [ -d "$ROOT/shared/projects/$n" ] && echo "$n" && break; done)"  # the synced project dir (environment/ may hold other dirs, e.g. B14's backfill/)
SRC="$ROOT/shared/projects/$PROJECT"
if [ -z "$PROJECT" ]; then  # generated instances (tasks/generated/*) carry their project under environment/ only
  PROJECT="$(for d in "$ROOT/$TASK"/environment/*/; do [ -f "$d/run.py" ] && basename "$d" && break; done)"; SRC="$ROOT/$TASK/environment/$PROJECT"
fi
WORK="$(mktemp -d)"; export APP_DIR="$WORK/app" FIXTURES_DIR="$ROOT/$TASK/tests/fixtures"
export ZENML_CONFIG_PATH="$WORK/zenml" ZENML_ANALYTICS_OPT_IN=false ZENML_LOGGING_VERBOSITY=ERROR
cp -r "$SRC" "$APP_DIR"; rm -rf "$APP_DIR/.zen" "$APP_DIR/fixtures"
(cd "$APP_DIR" && "$ROOT/.venv/bin/zenml" init >/dev/null 2>&1)
[ -f "$ROOT/$TASK/environment/setup_store.sh" ] && (cd "$APP_DIR" && PATH="$ROOT/.venv/bin:$PATH" bash "$ROOT/$TASK/environment/setup_store.sh" >/dev/null 2>&1)
[ -n "$PATCH" ] && PATH="$ROOT/.venv/bin:$PATH" bash "$ROOT/$PATCH"
"$ROOT/.venv/bin/python" -m pytest -q "$ROOT/$TASK/tests" -p no:cacheprovider >"$WORK/pytest.log" 2>&1
status=$?
printf '%-45s reward=%s\n' "${PATCH:-<noop>}" "$([ $status -eq 0 ] && echo 1 || echo 0)"
[ -n "${VERBOSE:-}" ] && grep -E 'passed|failed|Error|assert' "$WORK/pytest.log" | tail -8
[ -n "${KEEP:-}" ] && echo "kept $WORK" || rm -rf "$WORK"
