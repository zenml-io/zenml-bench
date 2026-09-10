FROM zenml-bench/base:0.96.4
# daily_report/ is synced from shared/projects/daily_report by scripts/sync_project.sh; do not edit it here.
COPY daily_report /app/daily_report
COPY setup_store.sh /opt/setup_store.sh
COPY backfill /opt/backfill
WORKDIR /app/daily_report
RUN zenml init && bash /opt/setup_store.sh
