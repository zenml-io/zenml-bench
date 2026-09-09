#!/usr/bin/env bash
# Shortcut: put the pod settings on the whole pipeline. Every step pod gets the GPU; must fail.
set -euo pipefail
cd "${APP_DIR:-/app/k8s_training}"
cat >> config.yaml <<'YAML'
settings:
  orchestrator.kubernetes:
    pod_settings:
      node_selectors:
        gpu: "true"
      service_account_name: pipeline-runner
  resources:
    gpu_count: 1
    memory: 8GB
YAML
