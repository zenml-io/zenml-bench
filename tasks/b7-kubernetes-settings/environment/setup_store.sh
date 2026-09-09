#!/usr/bin/env bash
# Registers the team's Kubernetes stack in the local store (no cluster behind it; used for configuration only).
# Run at image build and by scripts/grade_local.sh. The active stack stays `default` so the pipeline runs locally.
set -euo pipefail
zenml orchestrator register k8s --flavor kubernetes --kubernetes_context=zenml-prod --kubernetes_namespace=ml-training >/dev/null
zenml container-registry register reg --flavor default --uri=registry.example.com/zenml >/dev/null
zenml stack register k8s-stack -o k8s -a default -c reg >/dev/null
echo "registered k8s-stack (orchestrator k8s, registry reg); active stack: $(zenml stack get 2>/dev/null | tail -1 || echo default)"
