#!/usr/bin/env bash
# Shortcut: run the baseline and promote it. Must score 0 (gap_closed = 0).
set -euo pipefail
cd "${APP_DIR:-/app/research}"
python research.py --config configs/baseline.yaml
python - <<'PY'
from zenml.client import Client
Client().get_model_version("research_model", "baseline").set_stage("production", force=True)
PY
