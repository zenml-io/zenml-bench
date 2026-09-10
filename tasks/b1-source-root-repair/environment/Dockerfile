FROM zenml-bench/base:0.96.4
# analytics_workspace/ is synced from shared/projects/analytics_workspace by scripts/sync_project.sh; do not edit it here.
# The workspace root is /app (analytics/ and legacy_reports/ side by side); no `zenml init` at /app on purpose.
COPY analytics_workspace /app
COPY setup_store.sh /opt/setup_store.sh
WORKDIR /app
RUN bash /opt/setup_store.sh
