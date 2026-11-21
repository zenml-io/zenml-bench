FROM us-docker.pkg.dev/zenml-core/kitaru-bench/base:0.27.7-1@sha256:f8a65cef9a5be0b4129943c3a201f3b38e4c69dc1a25f4676bdc45d7dec569d9

# ---- world: helpdesk-live ----
# The assistant in /app/releases really runs here. The finance service records every refund and escalation in a
# root-only file; the world's start.sh wraps the base one to keep that service up. The history is recorded by
# running the assistant once per request while the image is built, so replays can match recorded tool calls.
COPY world/ /opt/world/
COPY --chown=agent:agent workspace/ /app/
RUN set -e; mkdir -p /opt/helpdesk && cp /opt/world/old/ledger_service.py /opt/helpdesk/ && mv /opt/kitaru-bench/start.sh /opt/kitaru-bench/start-base.sh \
    && cp /opt/world/old/start.sh /opt/kitaru-bench/start.sh && chmod 755 /opt/kitaru-bench/start.sh /opt/kitaru-bench/start-base.sh && chmod 700 /opt/helpdesk; \
    for i in $(seq 60); do WORKER_NAME=world-loader /opt/kitaru-bench/start.sh && break; sleep 2; done; \
    python /opt/world/load.py; /opt/kitaru-bench/stop.sh; \
    rm -rf /opt/world /var/log/kitaru-bench/* /etc/kitaru-bench/server.env /tmp/*

# ---- task: f2-fix-euro-with-evidence ----
# Registers the team's `refund-amount` evaluator. The setup files are deleted afterwards.
COPY setup/ /opt/setup/
RUN set -e; for i in $(seq 60); do WORKER_NAME=world-loader /opt/kitaru-bench/start.sh && break; sleep 2; done; \
    bash /opt/setup/setup.sh; /opt/kitaru-bench/stop.sh; \
    rm -rf /opt/setup /var/log/kitaru-bench/* /etc/kitaru-bench/server.env /tmp/*
