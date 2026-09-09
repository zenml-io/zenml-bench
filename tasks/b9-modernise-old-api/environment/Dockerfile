FROM zenml-bench/base:0.96.4
# legacy_training/ is synced from shared/projects/legacy_training by scripts/sync_project.sh; do not edit it here.
COPY legacy_training /app/legacy_training
WORKDIR /app/legacy_training
RUN zenml init
