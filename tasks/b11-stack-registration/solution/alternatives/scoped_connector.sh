#!/usr/bin/env bash
# Alternative: the connector itself is scoped to the bucket (--resource-type s3-bucket --resource-id <bucket>) and
# the store is connected without naming the resource; `connect` then fills the resource id from the store's path.
set -euo pipefail
cd "${APP_DIR:-/app/stack_onboarding}"
zenml service-connector register aws-platform --type aws --auth-method secret-key --region=eu-central-1 \
  --aws_access_key_id=AKIAPLACEHOLDER000001 --aws_secret_access_key=placeholder-secret-rotate-me \
  --resource-type s3-bucket --resource-id ml-platform-artifacts --no-verify
zenml artifact-store register s3-artifacts --flavor s3 --path=s3://ml-platform-artifacts/zenml
zenml artifact-store connect s3-artifacts --connector aws-platform --no-verify
zenml orchestrator register k8s-prod --flavor kubernetes --kubernetes_context=prod-eks --kubernetes_namespace=ml-prod --synchronous=false
zenml container-registry register ecr-prod --flavor aws --uri=123456789012.dkr.ecr.eu-central-1.amazonaws.com
zenml stack register prod-k8s -a s3-artifacts -o k8s-prod -c ecr-prod
zenml stack set prod-k8s
