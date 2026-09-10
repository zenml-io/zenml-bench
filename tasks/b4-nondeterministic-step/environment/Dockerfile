FROM zenml-bench/base:0.96.4
# sampling/ is synced from shared/projects/sampling by scripts/sync_project.sh; do not edit it here.
COPY sampling /app/sampling
WORKDIR /app/sampling
RUN zenml init
