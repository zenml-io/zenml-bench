#!/usr/bin/env bash
# Regression for the shared-store cache: a correct fix must still pass after the agent has run the
# pipeline itself (the grader's first run then hits the agent's cache). Found by the first Codex baseline.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"  # reference.sh exists when run via verify_task.py
bash "$REF"
cd "${APP_DIR:-/app/nightly}"
python run.py && python run.py
