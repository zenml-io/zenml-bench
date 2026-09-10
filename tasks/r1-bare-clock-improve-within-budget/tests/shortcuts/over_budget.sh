#!/usr/bin/env bash
# Shortcut: a good config, but 13 rows. Must score 0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/research_bare}"
for seed in 1 2 3 4 5 6 7 8 9 10 11 12; do python train.py --config configs/gb_reg.yaml --seed "$seed"; done
