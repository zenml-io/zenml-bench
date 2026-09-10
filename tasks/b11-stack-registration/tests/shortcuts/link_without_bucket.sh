#!/usr/bin/env bash
# Shortcut (Python route): the connector is recorded on the store but neither the store nor the connector names
# the bucket, so at run time ZenML could not pick an S3 resource. Must fail the effective-bucket check.
set -euo pipefail
cd "${APP_DIR:-/app/stack_onboarding}"
python - <<'PY'
from zenml.client import Client
from zenml.enums import StackComponentType as T
c = Client()
conn, _ = c.create_service_connector(name="aws-platform", connector_type="aws", auth_method="secret-key", verify=False,
    configuration={"aws_access_key_id": "AKIAPLACEHOLDER000001", "aws_secret_access_key": "placeholder-secret-rotate-me", "region": "eu-central-1"})
store = c.create_stack_component(name="s3-artifacts", flavor="s3", component_type=T.ARTIFACT_STORE, configuration={"path": "s3://ml-platform-artifacts/zenml"})
c.update_stack_component(name_id_or_prefix=store.id, component_type=T.ARTIFACT_STORE, connector_id=conn.id)
orch = c.create_stack_component(name="k8s-prod", flavor="kubernetes", component_type=T.ORCHESTRATOR, configuration={"kubernetes_context": "prod-eks", "kubernetes_namespace": "ml-prod", "synchronous": False})
reg = c.create_stack_component(name="ecr-prod", flavor="default", component_type=T.CONTAINER_REGISTRY, configuration={"uri": "123456789012.dkr.ecr.eu-central-1.amazonaws.com"})
stack = c.create_stack(name="prod-k8s", components={T.ARTIFACT_STORE: store.id, T.ORCHESTRATOR: orch.id, T.CONTAINER_REGISTRY: reg.id})
c.activate_stack(stack.id)
PY
