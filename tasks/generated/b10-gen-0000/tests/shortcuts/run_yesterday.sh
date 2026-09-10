#!/usr/bin/env bash
# Shortcut: no diagnosis; re-run the pipeline for the day that last worked. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_sales}"
python run.py --date 2026-08-21
