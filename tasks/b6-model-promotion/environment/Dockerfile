FROM zenml-bench/base:0.96.4
# model_promotion/ is synced from shared/projects/model_promotion by scripts/sync_project.sh; do not edit it here.
COPY model_promotion /app/model_promotion
COPY setup_store.sh /opt/setup_store.sh
WORKDIR /app/model_promotion
RUN zenml init && bash /opt/setup_store.sh
