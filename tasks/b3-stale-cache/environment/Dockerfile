FROM zenml-bench/base:0.96.4
# nightly/ is synced from shared/projects/nightly by scripts/sync_project.sh; do not edit it here.
COPY nightly /app/nightly
WORKDIR /app/nightly
RUN zenml init
