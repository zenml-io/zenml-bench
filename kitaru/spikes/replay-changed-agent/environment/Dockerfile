FROM python:3.13-slim
ARG KITARU_PIN=0.27.7
ARG KITARU_PYDANTIC_AI_PIN=0.4.0
RUN apt-get update && apt-get install -y --no-install-recommends bash curl ca-certificates procps util-linux postgresql && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "kitaru[cli,server,worker]==${KITARU_PIN}" "kitaru-pydantic-ai==${KITARU_PYDANTIC_AI_PIN}" uv
RUN PGV=$(ls /usr/lib/postgresql) && pg_ctlcluster $PGV main start \
    && su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'not-the-default-7f3a'\"" && pg_ctlcluster $PGV main stop
COPY server.env /etc/kitaru-bench/server.env
COPY start.sh /opt/kitaru-bench/start.sh
RUN chmod 700 /opt/kitaru-bench/start.sh && chmod 600 /etc/kitaru-bench/server.env
ENV KITARU_API_URL=http://127.0.0.1:8000 KITARU_API_KEY=bench KITARU_DISABLE_CLIENT_ANALYTICS=1 DO_NOT_TRACK=1 PYTHONPATH=/app
WORKDIR /app
COPY spike_agent /app/spike_agent
COPY refund_amount_evaluator.py run_spike4.py /app/
