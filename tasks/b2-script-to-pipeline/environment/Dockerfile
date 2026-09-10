FROM zenml-bench/base:0.96.4
# credit_script/ is synced from shared/projects/credit_script by scripts/sync_project.sh; do not edit it here.
COPY credit_script /app/credit_script
WORKDIR /app/credit_script
RUN zenml init
