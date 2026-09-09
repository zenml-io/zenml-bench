FROM zenml-bench/base:0.96.4
# churn_scoring/ is synced from shared/projects/churn_scoring by scripts/sync_project.sh; do not edit it here.
COPY churn_scoring /app/churn_scoring
WORKDIR /app/churn_scoring
RUN zenml init
