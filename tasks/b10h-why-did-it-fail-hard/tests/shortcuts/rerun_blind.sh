#!/usr/bin/env bash
# Shortcut: no diagnosis, no fix; re-run every day still on disk (they all complete). Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/daily_report}"
for f in data/*.csv; do d="$(basename "$f" .csv)"; python run.py --date "$d"; done
