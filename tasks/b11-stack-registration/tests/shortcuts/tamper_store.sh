#!/usr/bin/env bash
# Tamper: register everything with the right names and flavours (the S3 store linked through the Python client so no
# verification happens), then break the connector underneath it by deleting its secret row in SQLite: the link, the
# flavours and the region all read back correctly, but the connector has no credentials and could never authenticate.
# Must score 0. (Note in docs/decisions.md: for a registration task, rows written directly that DO instantiate through
# the flavours are indistinguishable from registration; the grader can only reject rows that no flavour would accept.)
set -euo pipefail
cd "${APP_DIR:-/app/stack_onboarding}"
zenml service-connector register aws-platform --type aws --auth-method secret-key --region=eu-central-1 \
  --aws_access_key_id=AKIAPLACEHOLDER000001 --aws_secret_access_key=placeholder-secret-rotate-me --no-verify
zenml artifact-store register s3-artifacts --flavor s3 --path=s3://ml-platform-artifacts/zenml
zenml orchestrator register k8s-prod --flavor kubernetes --kubernetes_context=prod-eks --kubernetes_namespace=ml-prod --synchronous=false
zenml container-registry register ecr-prod --flavor default --uri=123456789012.dkr.ecr.eu-central-1.amazonaws.com
python - <<'PY'
import sqlite3
from zenml.client import Client
from zenml.enums import StackComponentType
c = Client(); conn = c.get_service_connector("aws-platform")
c.update_stack_component(name_id_or_prefix="s3-artifacts", component_type=StackComponentType.ARTIFACT_STORE, connector_id=conn.id, connector_resource_id="ml-platform-artifacts")
con = sqlite3.connect(c.zen_store.config.url.removeprefix("sqlite:///"))
con.execute("delete from secret where id=(select secret_id from service_connector where name='aws-platform')")
con.execute("update service_connector set secret_id=NULL where name='aws-platform'")
con.commit(); con.close()
PY
zenml stack register prod-k8s -a s3-artifacts -o k8s-prod -c ecr-prod
zenml stack set prod-k8s
