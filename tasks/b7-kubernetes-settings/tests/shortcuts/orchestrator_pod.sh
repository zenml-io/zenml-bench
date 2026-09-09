#!/usr/bin/env bash
# Shortcut: configure the orchestrator pod instead of the train step pod. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app/k8s_training}"
cat >> config.yaml <<'YAML'
settings:
  orchestrator.kubernetes:
    orchestrator_pod_settings:
      node_selectors:
        gpu: "true"
      service_account_name: pipeline-runner
      resources:
        requests: {nvidia.com/gpu: "1", memory: 8Gi}
YAML
