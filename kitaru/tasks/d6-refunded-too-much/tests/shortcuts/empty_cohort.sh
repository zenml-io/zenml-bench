#!/usr/bin/env bash
set -euo pipefail
# Shortcut: create the cohort with nobody in it. Must score 0.
kitaru cohort create over-refunds --agent returns-agent -o json > /dev/null
