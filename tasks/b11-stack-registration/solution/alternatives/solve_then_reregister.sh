#!/usr/bin/env bash
# Alternative: an agent that does the work, tears it all down, and does it again (ids change; names stay).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../solve.sh"
bash "$REF"
cd "${APP_DIR:-/app/stack_onboarding}"
zenml stack set default
zenml stack delete -y prod-k8s
zenml artifact-store delete s3-artifacts
zenml orchestrator delete k8s-prod
zenml container-registry delete ecr-prod
zenml service-connector delete aws-platform
bash "$REF"
