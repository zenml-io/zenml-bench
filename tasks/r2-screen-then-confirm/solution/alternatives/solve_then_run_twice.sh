#!/usr/bin/env bash
# The reference, then two more runs of the same config on further seeds (five runs on one version, still in budget).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/research}"
python research.py --config configs/gb_reg.yaml --seed 3
python research.py --config configs/gb_reg.yaml --seed 4
