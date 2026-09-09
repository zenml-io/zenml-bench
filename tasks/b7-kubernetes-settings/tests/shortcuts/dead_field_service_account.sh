#!/usr/bin/env bash
# Shortcut: `pod_settings.service_account_name`. KubernetesPodSettings has no such field; ZenML accepts the
# unknown key silently and the orchestrator never reads it. Looks right, does nothing on a cluster. Must fail.
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
        memory: 8GB
YAML
