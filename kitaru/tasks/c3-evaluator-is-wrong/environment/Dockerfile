FROM docker.io/zenmldocker/kitaru-bench-base:0.27.7-1@sha256:f8a65cef9a5be0b4129943c3a201f3b38e4c69dc1a25f4676bdc45d7dec569d9

# ---- world: storefront ----
# The history is imported while the image is built, so a task starts with a loaded workspace. The
# session files are deleted afterwards; the code that planned them (story.py) never enters the image.
COPY world/ /opt/world/
COPY --chown=agent:agent workspace/ /app/
RUN set -e; for i in $(seq 60); do WORKER_NAME=world-loader /opt/kitaru-bench/start.sh && break; sleep 2; done; \
    python /opt/world/load.py; /opt/kitaru-bench/stop.sh; \
    rm -rf /opt/world /var/log/kitaru-bench/* /etc/kitaru-bench/server.env /tmp/*; \
    chown -R agent:agent /app && cd /app && runuser -u agent -- sh -c 'git init -q && git add -A && git -c user.name=larkspur -c user.email=dev@larkspur.example commit -q -m "Returns assistant workspace"'
