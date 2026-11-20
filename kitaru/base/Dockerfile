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
    postgresql nodejs npm tmux ripgrep && rm -rf /var/lib/apt/lists/*
RUN pip install "kitaru[cli,server,worker,mcp]==${KITARU_PIN}" "kitaru-pydantic-ai==${KITARU_PYDANTIC_AI_PIN}" "uv==${UV_PIN}" pytest
# Agent CLIs baked in: Harbor skips its own install when the binary is on PATH, and the container is sealed.
RUN npm install -g @anthropic-ai/claude-code@2.1.329 @openai/codex@0.171.0 && claude --version && codex --version
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
ENV KITARU_API_URL=http://127.0.0.1:8000 KITARU_API_KEY=bench KITARU_ANALYTICS_OPT_IN=false
WORKDIR /app
