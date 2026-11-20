# Base image for every Kitaru task. The Kitaru pin lives HERE and nowhere else.
# One container holds PostgreSQL, the Kitaru server, a worker and the agent under test
# (docs/decisions.md 2026-11-20). Nothing starts by itself: Harbor replaces the entrypoint, so each
# task's [environment.healthcheck] runs /opt/kitaru-bench/start.sh, which starts what is missing.
FROM python:3.13-slim
ARG KITARU_PIN=0.27.7
ARG KITARU_PYDANTIC_AI_PIN=0.4.0
ARG UV_PIN=0.13.9
ARG KITARU_DOCS_TAG=python/kitaru/v0.27.7
ENV KITARU_PIN=${KITARU_PIN} PIP_NO_CACHE_DIR=1
# nodejs/npm: claude-code + codex; tmux: terminus-2; ripgrep: codex; jq/git: what an agent reaches for.
RUN apt-get update && apt-get install -y --no-install-recommends bash curl git ca-certificates procps util-linux jq \
    postgresql nodejs npm tmux ripgrep && rm -rf /var/lib/apt/lists/* \
    # Installing PostgreSQL makes Debian generate a private key for TLS. Postgres here only listens on
    # 127.0.0.1, so TLS is switched off and the key is deleted in this same step: a key deleted in a
    # later step would still sit in this layer of a public image.
    && sed -i "s/^ssl = on/ssl = off/" /etc/postgresql/*/main/postgresql.conf \
    && rm -f /etc/ssl/private/ssl-cert-snakeoil.key /etc/ssl/certs/ssl-cert-snakeoil.pem
RUN pip install "kitaru[cli,server,worker,mcp]==${KITARU_PIN}" "kitaru-pydantic-ai==${KITARU_PYDANTIC_AI_PIN}" "uv==${UV_PIN}" pytest
# Agent CLIs baked in: Harbor skips its own install when the binary is on PATH, and the container is sealed.
RUN npm install -g @anthropic-ai/claude-code@2.1.329 @openai/codex@0.171.0 && claude --version && codex --version \
    && npm cache clean --force && rm -rf /root/.npm
# Built-in evaluators, importers and analyzers are pinned packages the worker installs when a job runs.
# Their wheels live here, and /etc/uv/uv.toml points every uv call at this folder (decisions.md, spike 2).
RUN pip download --only-binary=:all: -d /opt/kitaru-wheels "kitaru[cli,server,worker]==${KITARU_PIN}" \
    kitaru-evaluator==0.3.0 kitaru-jsonl-importer==0.2.0 kitaru-langfuse-importer==0.5.0 kitaru-langsmith-importer==0.4.0 \
    kitaru-phoenix-importer==0.4.0 kitaru-braintrust-importer==0.4.0 kitaru-logfire-importer==0.4.1 kitaru-mlflow-importer==0.1.0 \
    kitaru-post-import-insights==0.4.0 && chmod -R a+rX /opt/kitaru-wheels
COPY base/files/uv.toml /etc/uv/uv.toml
# Offline documentation: Kitaru's docs/book at the pinned release tag, plain Markdown.
RUN mkdir -p /opt/kitaru-docs && curl -fsSL "https://github.com/zenml-io/kitaru/archive/refs/tags/${KITARU_DOCS_TAG}.tar.gz" \
    | tar -xz -C /opt/kitaru-docs --strip-components=3 --wildcards '*/docs/book/*' && test -f /opt/kitaru-docs/README.md && chmod -R a+rX /opt/kitaru-docs
# Three accounts. root: Postgres control, the server, the grader. agent: the agent under test and the
# worker it may restart. grader: the worker the grader starts for its own jobs, so code the agent
# registered never runs as root.
RUN useradd -m -s /bin/bash agent && useradd -m -s /bin/bash grader && mkdir -p /app /etc/kitaru-bench /var/log/kitaru-bench && chown agent:agent /app
COPY base/files/start.sh base/files/stop.sh /opt/kitaru-bench/
RUN chmod 755 /opt/kitaru-bench/start.sh && chmod 700 /opt/kitaru-bench/stop.sh
# Telemetry off, for everything that runs in the container. Kitaru's client reads
# KITARU_DISABLE_CLIENT_ANALYTICS and DO_NOT_TRACK (src/kitaru/client/config.py); the server's switch,
# KITARU_SERVER_ANALYTICS_OPT_IN=false, is set by start.sh. The DISABLE_* names are Claude Code's.
# KITARU_API_KEY is a placeholder, not a secret: the server runs with authentication off.
ENV KITARU_API_URL=http://127.0.0.1:8000 KITARU_API_KEY=bench \
    KITARU_DISABLE_CLIENT_ANALYTICS=1 DO_NOT_TRACK=1 \
    DISABLE_TELEMETRY=1 DISABLE_ERROR_REPORTING=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
WORKDIR /app

# ---- world: storefront ----
# The history is imported while the image is built, so a task starts with a loaded workspace. The
# session files are deleted afterwards; the code that planned them (story.py) never enters the image.
COPY world/ /opt/world/
COPY --chown=agent:agent workspace/ /app/
RUN set -e; for i in $(seq 60); do WORKER_NAME=world-loader /opt/kitaru-bench/start.sh && break; sleep 2; done; \
    python /opt/world/load.py; /opt/kitaru-bench/stop.sh; \
    rm -rf /opt/world /var/log/kitaru-bench/* /etc/kitaru-bench/server.env /tmp/*; \
    chown -R agent:agent /app && cd /app && runuser -u agent -- sh -c 'git init -q && git add -A && git -c user.name=larkspur -c user.email=dev@larkspur.example commit -q -m "Returns assistant workspace"'
