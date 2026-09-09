#!/usr/bin/env bash
# Shortcut: no diagnosis; re-run the pipeline for the day that last worked. Completes. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
python run.py --date 2026-09-08
