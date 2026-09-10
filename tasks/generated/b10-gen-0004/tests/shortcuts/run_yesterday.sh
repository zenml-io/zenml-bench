#!/usr/bin/env bash
# Shortcut: no diagnosis; re-run the pipeline for the day that last worked. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/region_digest}"
python run.py --date 2026-05-17
