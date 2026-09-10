#!/usr/bin/env bash
# The reference config on three screening seeds (three runs attach to one model version), then promote.
# The graded artifact is the newest of the three; prepare_data is CACHED on runs 2 and 3.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/research}"
python research.py --config configs/gb_reg.yaml --seed 1
python research.py --config configs/gb_reg.yaml --seed 2
