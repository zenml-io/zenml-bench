#!/usr/bin/env bash
# usage: scripts/sync_checks.sh
# Copies shared/checks/store_integrity.py into tests/ of every task that imports it (Harbor uploads tests/ alone,
# so each task carries its own copy). shared/checks/ is the source of truth; never edit the copies.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for t in "$ROOT"/tasks/*/ "$ROOT"/tasks/generated/*/; do
  [ -d "$t/tests" ] || continue
  grep -qs "store_integrity" "$t"/tests/test_*.py 2>/dev/null || continue
  cp "$ROOT/shared/checks/store_integrity.py" "$t/tests/store_integrity.py"
  echo "synced -> ${t#$ROOT/}tests/store_integrity.py"
done
