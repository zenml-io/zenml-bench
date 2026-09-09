FROM zenml-bench/base:0.96.4
# k8s_training/ is synced from shared/projects/k8s_training by scripts/sync_project.sh; do not edit it here.
COPY k8s_training /app/k8s_training
COPY setup_store.sh /opt/setup_store.sh
WORKDIR /app/k8s_training
RUN zenml init && bash /opt/setup_store.sh
