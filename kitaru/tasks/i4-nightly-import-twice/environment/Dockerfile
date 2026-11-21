FROM us-docker.pkg.dev/zenml-core/kitaru-bench/base:0.27.7-1@sha256:f8a65cef9a5be0b4129943c3a201f3b38e4c69dc1a25f4676bdc45d7dec569d9

# ---- world: exports ----
# The agent is registered while the image is built. The
# loader is deleted afterwards; the code that plans the logs (story.py) never enters the image.
COPY world/ /opt/world/
COPY --chown=agent:agent workspace/ /app/
RUN set -e; for i in $(seq 60); do WORKER_NAME=world-loader /opt/kitaru-bench/start.sh && break; sleep 2; done; \
    python /opt/world/load.py; /opt/kitaru-bench/stop.sh; \
    rm -rf /opt/world /var/log/kitaru-bench/* /etc/kitaru-bench/server.env /tmp/*; \
    chown -R agent:agent /app && cd /app && runuser -u agent -- sh -c 'git init -q && git add -A && git -c user.name=tidewater -c user.email=dev@tidewater.example commit -q -m "Dispatch assistant workspace"'

# ---- task: i4-nightly-import-twice ----
# Imports five nights correctly, makes the reviewed cohort, then imports two nights with the changed script. The setup files are deleted afterwards.
COPY setup/ /opt/setup/
RUN set -e; for i in $(seq 60); do WORKER_NAME=world-loader /opt/kitaru-bench/start.sh && break; sleep 2; done; \
    bash /opt/setup/setup.sh; /opt/kitaru-bench/stop.sh; \
    rm -rf /opt/setup /var/log/kitaru-bench/* /etc/kitaru-bench/server.env /tmp/*
