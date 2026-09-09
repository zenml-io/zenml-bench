#!/usr/bin/env bash
# Shortcut: GPU and memory via resource settings only; no node selector or service account. Must fail.
set -euo pipefail
cd "${APP_DIR:-/app/k8s_training}"
cat >> config.yaml <<'YAML'
steps:
  train:
    settings:
      resources:
        gpu_count: 1
        memory: 8GB  # ResourceSettings wants GB; the pod spec form would be 8Gi
YAML
