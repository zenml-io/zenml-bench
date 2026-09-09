#!/usr/bin/env bash
# Shortcut: node selector and GPU on the train step, but the service account via the top-level
# `service_account_name`, which also changes the orchestrator pod. Must fail the orchestrator-pod check.
set -euo pipefail
cd "${APP_DIR:-/app/k8s_training}"
cat >> config.yaml <<'YAML'
settings:
  orchestrator.kubernetes:
    service_account_name: pipeline-runner
steps:
  train:
    settings:
      orchestrator.kubernetes:
        pod_settings:
          node_selectors:
            gpu: "true"
      resources:
        gpu_count: 1
        memory: 8GB
YAML
