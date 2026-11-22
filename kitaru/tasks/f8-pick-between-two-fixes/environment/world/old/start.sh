#!/usr/bin/env bash
# The helpdesk-services world's start script. It replaces the base image's /opt/kitaru-bench/start.sh (kept as
# start-base.sh): the same checks, plus the finance service and the order service. Both keep their files where only root can read them.
/opt/kitaru-bench/start-base.sh "$@"; rc=$?
pgrep -f "/opt/helpdesk/ledger_service.py" > /dev/null || ( cd / && setsid nohup python /opt/helpdesk/ledger_service.py >> /var/log/kitaru-bench/finance.log 2>&1 < /dev/null & )
pgrep -f "/opt/helpdesk/order_service.py" > /dev/null || ( cd / && setsid nohup python /opt/helpdesk/order_service.py >> /var/log/kitaru-bench/orders.log 2>&1 < /dev/null & )
curl -fsS -m 3 http://127.0.0.1:8091/health > /dev/null 2>&1 || exit 1
curl -fsS -m 3 http://127.0.0.1:8092/health > /dev/null 2>&1 || exit 1
exit $rc
