#!/usr/bin/env bash
# Shortcut: run the baseline and promote it. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/research_bare}"
python train.py --config configs/baseline.yaml
cp models/baseline-seed0.pkl best_model.pkl
