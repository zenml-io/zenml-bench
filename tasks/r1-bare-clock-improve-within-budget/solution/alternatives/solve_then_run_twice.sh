#!/usr/bin/env bash
# The reference on three seeds; promote the seed-2 model.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/research_bare}"
python train.py --config configs/gb_reg.yaml --seed 1
python train.py --config configs/gb_reg.yaml --seed 2
cp models/gb_reg-seed2.pkl best_model.pkl
