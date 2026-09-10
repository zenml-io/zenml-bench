FROM zenml-bench/base:0.96.4
# research/ is synced from shared/projects/research by scripts/sync_project.sh; do not edit it here.
COPY research /app/research
WORKDIR /app/research
RUN zenml init
