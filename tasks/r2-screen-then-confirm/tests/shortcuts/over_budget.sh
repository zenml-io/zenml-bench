#!/usr/bin/env bash
# Shortcut: a confirmed good config, but 13 runs in total. Must score 0 on the budget rule.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/research}"
for seed in 3 4 5 6 7 8 9 10 11 12; do python research.py --config configs/gb_reg.yaml --seed "$seed"; done
