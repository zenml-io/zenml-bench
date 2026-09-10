#!/usr/bin/env bash
# Alternative: behaves like a real agent. Tries `register --connector` first, sees the verification error and the
# missing link, then repairs it with `connect --no-verify`; also sets the stack globally as well as for the project.
set -euo pipefail
cd "${APP_DIR:-/app/stack_onboarding}"
zenml service-connector register aws-platform --type aws --auth-method secret-key --region=eu-central-1 \
  --aws_access_key_id=AKIAPLACEHOLDER000001 --aws_secret_access_key=placeholder-secret-rotate-me --no-verify
zenml artifact-store register s3-artifacts --flavor s3 --path=s3://ml-platform-artifacts/zenml --connector aws-platform || true
zenml artifact-store describe s3-artifacts
zenml artifact-store connect s3-artifacts --connector aws-platform --resource-id s3://ml-platform-artifacts --no-verify
zenml orchestrator register k8s-prod --flavor kubernetes --kubernetes_context=prod-eks --kubernetes_namespace=ml-prod --synchronous=False
zenml container-registry register ecr-prod --flavor default --uri=123456789012.dkr.ecr.eu-central-1.amazonaws.com
zenml stack register prod-k8s -a s3-artifacts -o k8s-prod -c ecr-prod
zenml stack set prod-k8s
(cd / && zenml stack set prod-k8s)
zenml stack describe prod-k8s
