#!/usr/bin/env bash
set -euo pipefail
kitaru evaluator register refund-amount --script /app/evaluators/refund_amount.py --entrypoint evaluate --description "Passes when every refund is the order's total." -o json > /dev/null
echo "refund-amount registered"
