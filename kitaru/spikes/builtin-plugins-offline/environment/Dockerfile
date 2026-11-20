FROM python:3.13-slim
ARG KITARU_PIN=0.27.7
ARG KITARU_PYDANTIC_AI_PIN=0.4.0
RUN apt-get update && apt-get install -y --no-install-recommends bash curl ca-certificates procps util-linux postgresql && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "kitaru[cli,server,worker]==${KITARU_PIN}" "kitaru-pydantic-ai==${KITARU_PYDANTIC_AI_PIN}" uv==0.13.9
RUN PGV=$(ls /usr/lib/postgresql) && pg_ctlcluster $PGV main start \
    && su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'not-the-default-7f3a'\"" && pg_ctlcluster $PGV main stop
# Every built-in evaluator, importer and analyzer is a pinned package that the worker installs when a job
# runs (`uv run --with <package>==<version>`). With the network sealed that download fails, so the wheels
# for all nine packages and everything they depend on are stored here, and /etc/uv/uv.toml tells every uv
# call in the container to look only here. (The UV_NO_INDEX variable is ignored by `uv run` in uv 0.13.9.)
RUN pip download --no-cache-dir --only-binary=:all: -d /opt/kitaru-wheels "kitaru[cli,server,worker]==${KITARU_PIN}" \
    kitaru-evaluator==0.3.0 kitaru-jsonl-importer==0.2.0 kitaru-langfuse-importer==0.5.0 kitaru-langsmith-importer==0.4.0 \
    kitaru-phoenix-importer==0.4.0 kitaru-braintrust-importer==0.4.0 kitaru-logfire-importer==0.4.1 kitaru-mlflow-importer==0.1.0 \
    kitaru-post-import-insights==0.4.0 && chmod -R a+rX /opt/kitaru-wheels && ls /opt/kitaru-wheels | wc -l && du -sh /opt/kitaru-wheels
RUN mkdir -p /etc/uv && printf 'no-index = true\nfind-links = ["/opt/kitaru-wheels"]\n' > /etc/uv/uv.toml
COPY server.env /etc/kitaru-bench/server.env
COPY start.sh /opt/kitaru-bench/start.sh
RUN chmod 700 /opt/kitaru-bench/start.sh && chmod 600 /etc/kitaru-bench/server.env
ENV KITARU_API_URL=http://127.0.0.1:8000 KITARU_API_KEY=bench KITARU_ANALYTICS_OPT_IN=false PYTHONPATH=/app
WORKDIR /app
COPY spike_agent /app/spike_agent
COPY run_spike2.py /app/
