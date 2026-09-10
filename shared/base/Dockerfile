# Base image for every zenml-bench task. The ZenML pin lives HERE and nowhere else.
# nodejs/npm/procps: claude-code + codex install needs; tmux: terminus-2; ripgrep: codex. Baked in so
# agent setup needs no network inside the container.
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim
ARG ZENML_PIN=0.96.4
ENV ZENML_PIN=${ZENML_PIN} \
    ZENML_ANALYTICS_OPT_IN=false \
    ZENML_LOGGING_VERBOSITY=WARNING \
    PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends bash curl git ca-certificates nodejs npm procps tmux ripgrep && rm -rf /var/lib/apt/lists/*
RUN pip install "zenml[local]==${ZENML_PIN}" pandas scikit-learn pytest kubernetes  # kubernetes: settings classes for Tier C tasks
# Agent CLIs baked in: Harbor skips its own install when the binary is on PATH, and the container is
# sealed during setup so a download would fail anyway. Bump these deliberately; record in decisions.md.
RUN npm install -g @anthropic-ai/claude-code@latest @openai/codex@latest && claude --version && codex --version
# Offline documentation snapshot. TODO(decisions): pin to the docs matching ZENML_PIN rather than "latest".
ADD https://docs.zenml.io/llms-full.txt /opt/zenml-docs/llms-full.txt
RUN chmod -R a+r /opt/zenml-docs
# ZenML MCP server for the "+ MCP" condition (run_baselines.py --condition mcp; config in shared/mcp/zenml.json).
# Pinned to a commit of zenml-io/mcp-zenml (v1.2.0); run with the image's own Python so it uses ZENML_PIN, not the
# server's own `zenml~=0.93` PEP 723 pin. It talks to the local SQLite store through `Client()`; only `get_step_logs`
# needs a REST server (see decisions.md 2026-09-10). Analytics off: the container has no network.
ARG MCP_ZENML_SHA=33c6c7f50f8732149fcbeef3e3f792553c8a2238
ENV ZENML_MCP_DISABLE_ANALYTICS=1
RUN pip install "mcp[cli]==1.26.0" \
    && git clone -q https://github.com/zenml-io/mcp-zenml.git /opt/mcp-zenml && git -C /opt/mcp-zenml checkout -q ${MCP_ZENML_SHA} \
    && rm -rf /opt/mcp-zenml/.git && python -c "import mcp.server.fastmcp"
