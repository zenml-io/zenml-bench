#!/usr/bin/env bash
# Reference: step-level Kubernetes pod settings plus resource settings in config.yaml.
set -euo pipefail
cd "${APP_DIR:-/app/k8s_training}"
cat >> config.yaml <<'YAML'
steps:
  train:
    settings:
      orchestrator.kubernetes:
        pod_settings:
          node_selectors:
            gpu: "true"
          service_account_name: pipeline-runner
      resources:
        gpu_count: 1
        memory: 8GB  # ResourceSettings wants GB; the pod spec form would be 8Gi
YAML
