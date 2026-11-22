#!/usr/bin/env bash
set -euo pipefail
kitaru agent register support-assistant --description "Tidewater Couriers support assistant" --display-version 1.5.0 --command "python -m support_assistant" --working-dir /app --tool lookup_shipment --tool open_claim --tool schedule_redelivery --tool send_email -o json > /dev/null
echo "support-assistant registered"
