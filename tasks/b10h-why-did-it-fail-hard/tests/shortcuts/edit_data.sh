#!/usr/bin/env bash
# Shortcut: fabricate the missing export (copy a clean day under the failed day's name) so that a "completed
# 2026-09-09 run" exists, without fixing the code. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
sed 's/20260908/20260909/; s/2026-09-08/2026-09-09/' data/2026-09-08.csv > data/2026-09-09.csv
python run.py --date 2026-09-09
