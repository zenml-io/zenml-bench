#!/usr/bin/env bash
# Installed in cron on the report box:  0 6 * * *  cd /app/daily_report && bin/nightly.sh >> /var/log/daily_report.log 2>&1
# The transfer job has already dropped yesterday's export into data/ by then.
set -euo pipefail
cd "$(dirname "$0")/.."
python run.py --date "$(date -d yesterday +%F)" --trigger scheduled
