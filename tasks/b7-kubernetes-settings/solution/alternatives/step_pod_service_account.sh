#!/usr/bin/env bash
# Alternative (what both harnesses did in the first baseline): `step_pod_service_account_name` on the step's
# orchestrator settings, resources inside the pod spec, only in limits for the GPU.
set -euo pipefail
cd "${APP_DIR:-/app/k8s_training}"
cat >> config.yaml <<'YAML'
steps:
  train:
    settings:
      orchestrator.kubernetes:
        step_pod_service_account_name: pipeline-runner
        pod_settings:
          node_selectors:
            gpu: "true"
          resources:
            requests:
              memory: 8Gi
            limits:
              memory: 8Gi
              nvidia.com/gpu: "1"
YAML
