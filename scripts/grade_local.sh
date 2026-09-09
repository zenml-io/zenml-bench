#!/usr/bin/env bash
# usage: scripts/grade_local.sh <task-dir> [patch-script]
# Copies the task's project to a temp dir, applies the patch (a solution or shortcut), grades it in a
# fresh ZenML store with the task's own tests, and prints the reward. No Docker, no Harbor.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK="$1"; PATCH="${2:-}"
WORK="$(mktemp -d)"; export APP_DIR="$WORK/app" FIXTURES_DIR="$ROOT/$TASK/tests/fixtures"
export ZENML_CONFIG_PATH="$WORK/zenml" ZENML_ANALYTICS_OPT_IN=false ZENML_LOGGING_VERBOSITY=ERROR
cp -r "$ROOT/shared/projects/nightly" "$APP_DIR"; rm -rf "$APP_DIR/.zen" "$APP_DIR/fixtures"
(cd "$APP_DIR" && "$ROOT/.venv/bin/zenml" init >/dev/null 2>&1)
[ -n "$PATCH" ] && PATH="$ROOT/.venv/bin:$PATH" bash "$ROOT/$PATCH"
"$ROOT/.venv/bin/python" -m pytest -q "$ROOT/$TASK/tests" -p no:cacheprovider >"$WORK/pytest.log" 2>&1
status=$?
printf '%-45s reward=%s\n' "${PATCH:-<noop>}" "$([ $status -eq 0 ] && echo 1 || echo 0)"
[ -n "${VERBOSE:-}" ] && grep -E 'passed|failed|Error|assert' "$WORK/pytest.log" | tail -8
[ -n "${KEEP:-}" ] && echo "kept $WORK" || rm -rf "$WORK"
