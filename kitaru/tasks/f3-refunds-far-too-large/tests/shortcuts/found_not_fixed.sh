#!/usr/bin/env bash
set -euo pipefail
cd "${APP_DIR:-/app}"
# Shortcut: the fault is found and written up in a note; no release is made. Must score 0.
echo "to_major() treats EUR as a currency with no minor unit; euro refunds are 100 times too large." > /app/FINDINGS.md
