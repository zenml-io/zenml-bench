"""Grader for B11 stack-registration. Reads the ZenML store with the client; nothing is grepped.

Facts the assertions rest on (docs/decisions.md 2026-09-10): a component's connector link is recorded as
`ComponentResponse.connector` (+ `connector_resource_id`); the CLI `connect` fills the resource id from the store's
`path` when none is given, the Python client records whatever it was handed, and a connector scoped with its own
`resource_id` needs none on the component, so the "effective bucket" accepts all three. The active stack is
per-repository when a `.zen` directory exists, so it is read from APP_DIR (test.sh cds there). The default stack
cannot be modified or renamed, only deleted once another stack is active globally.
Env: APP_DIR (default /app/stack_onboarding).
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from zenml.client import Client
from zenml.config.global_config import GlobalConfiguration
from zenml.enums import ExecutionStatus, StackComponentType
from zenml.service_connectors.service_connector_registry import service_connector_registry
from zenml.stack import Stack

APP_DIR = Path(os.environ.get("APP_DIR", "/app/stack_onboarding"))
os.chdir(APP_DIR)  # Client() is a singleton that binds to the repository it finds at first use; the active stack is per-repository
CONNECTOR, STORE, ORCH, REGISTRY, STACK = "aws-platform", "s3-artifacts", "k8s-prod", "ecr-prod", "prod-k8s"
BUCKET, PATH = "ml-platform-artifacts", "s3://ml-platform-artifacts/zenml"
REGION, KEY_ID = "eu-central-1", "AKIAPLACEHOLDER000001"
CONTEXT, NAMESPACE = "prod-eks", "ml-prod"
REGISTRY_URI = "123456789012.dkr.ecr.eu-central-1.amazonaws.com"
AS, OR, CR = StackComponentType.ARTIFACT_STORE, StackComponentType.ORCHESTRATOR, StackComponentType.CONTAINER_REGISTRY


def bucket_of(resource_id: str | None) -> str | None:
    """`ml-platform-artifacts`, `s3://ml-platform-artifacts`, `s3://ml-platform-artifacts/zenml` -> the bucket name."""
    if not resource_id:
        return None
    return resource_id.removeprefix("s3://").split("/", 1)[0]


def component(kind: StackComponentType, name: str) -> Any:
    try:
        return Client().get_stack_component(kind, name, allow_name_prefix_match=False)
    except KeyError:
        pytest.fail(f"no {kind.value} named {name!r}")


def falsy(v: Any) -> bool:
    return v in (False, "false", "False", 0, "0")


@pytest.fixture(scope="module")
def connector() -> Any:
    try:
        return Client().get_service_connector(CONNECTOR, allow_name_prefix_match=False, expand_secrets=True)
    except KeyError:
        pytest.fail(f"no service connector named {CONNECTOR!r}")


def test_connector(connector):
    ctype = connector.connector_type if isinstance(connector.connector_type, str) else connector.connector_type.connector_type
    assert ctype == "aws", f"connector type is {ctype}"
    assert connector.auth_method == "secret-key", f"auth method is {connector.auth_method}"
    cfg = {k: (v.get_secret_value() if hasattr(v, "get_secret_value") else v) for k, v in dict(connector.configuration).items()}
    assert cfg.get("region") == REGION, f"region is {cfg.get('region')}"
    assert cfg.get("aws_access_key_id") == KEY_ID, "access key id is not the placeholder from the handover"


def test_artifact_store_linked_to_connector(connector):
    store = component(AS, STORE)
    assert store.flavor_name == "s3", f"artifact store flavour is {store.flavor_name}"
    assert store.configuration.get("path") == PATH, f"path is {store.configuration.get('path')}"
    assert store.connector is not None, "artifact store has no service connector recorded (the link was never made)"
    assert store.connector.id == connector.id, f"artifact store is linked to connector {store.connector.name!r}"
    effective = bucket_of(store.connector_resource_id) or bucket_of(connector.resource_id)
    assert effective == BUCKET, f"linked resource resolves to bucket {effective!r}, not {BUCKET!r}"


def test_orchestrator():
    orch = component(OR, ORCH)
    assert orch.flavor_name == "kubernetes", f"orchestrator flavour is {orch.flavor_name}"
    cfg = orch.configuration
    assert cfg.get("kubernetes_context") == CONTEXT, f"kubernetes_context is {cfg.get('kubernetes_context')}"
    assert cfg.get("kubernetes_namespace") == NAMESPACE, f"kubernetes_namespace is {cfg.get('kubernetes_namespace')}"
    assert falsy(cfg.get("synchronous", True)), f"synchronous is {cfg.get('synchronous', '<default: true>')}"


def test_container_registry():
    reg = component(CR, REGISTRY)
    assert reg.flavor_name in {"default", "aws"}, f"registry flavour is {reg.flavor_name}"
    assert reg.configuration.get("uri") == REGISTRY_URI, f"uri is {reg.configuration.get('uri')}"


def test_stack_composition_and_active():
    try:
        stack = Client().get_stack(STACK, allow_name_prefix_match=False)
    except KeyError:
        pytest.fail(f"no stack named {STACK!r}")
    names = {t.value: [c.name for c in cs] for t, cs in stack.components.items()}
    assert names == {AS.value: [STORE], OR.value: [ORCH], CR.value: [REGISTRY]}, f"stack components are {names}"
    active = Client(root=APP_DIR).active_stack_model  # per-repository active stack, as `python run.py` there would see it
    assert active.name == STACK, f"active stack for {APP_DIR} is {active.name!r} (per-repository .zen/config.yaml, not the global one)"
    try:
        Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
        global_active = GlobalConfiguration().active_stack_id == stack.id
        Path("/logs/verifier/metrics.json").write_text(json.dumps({"global_active_too": int(bool(global_active))}))
    except Exception:
        pass


def test_records_instantiate_through_their_flavours(connector):
    """The store is writable by the agent (tests/shortcuts/tamper_store.sh edits rows in SQLite). Whatever wrote the
    rows, each component must instantiate through its flavour's config class and the connector through its connector
    type with its secret present, as `python run.py` on `prod-k8s` would need. (`Stack.validate()` needs a live kube
    context, so it is not called.)"""
    stack = Stack.from_model(Client().get_stack(STACK, allow_name_prefix_match=False))
    kinds = {t.value: type(c).__name__ for t, c in stack.components.items()}
    assert kinds.get(AS.value) == "S3ArtifactStore", f"artifact store instantiates as {kinds.get(AS.value)}"
    assert kinds.get(OR.value) == "KubernetesOrchestrator", f"orchestrator instantiates as {kinds.get(OR.value)}"
    sc = service_connector_registry.instantiate_connector(model=connector)
    assert sc.auth_method == "secret-key"
    cfg = sc.config.model_dump()
    assert cfg.get("aws_access_key_id") and cfg.get("aws_secret_access_key"), "connector instantiates without its secret"


def test_default_stack_intact():
    try:
        default = Client().get_stack("default", allow_name_prefix_match=False)
    except KeyError:
        pytest.fail("the default stack is gone")
    for kind, comps in default.components.items():
        assert [c.name for c in comps] == ["default"], f"default stack's {kind.value} is {[c.name for c in comps]}"
        assert comps[0].flavor_name == "local", f"default {kind.value} flavour is {comps[0].flavor_name}"
        assert comps[0].configuration == {}, f"default {kind.value} configuration changed: {comps[0].configuration}"
    seen = {r.id for r in Client().list_pipeline_runs(size=500).items}
    env = {**os.environ, "ZENML_ACTIVE_STACK_ID": str(default.id)}
    proc = subprocess.run([sys.executable, "run.py"], cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"run.py on the default stack failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in Client().list_pipeline_runs(sort_by="desc:created", size=5).items if r.id not in seen]
    assert len(new) == 1 and new[0].status == ExecutionStatus.COMPLETED and new[0].stack.name == "default"


def test_collateral_nothing_extra():
    stacks = {s.name for s in Client().list_stacks(size=100).items}
    assert stacks == {"default", STACK}, f"stacks registered: {sorted(stacks)}"
    comps = {(c.type.value, c.name) for c in Client().list_stack_components(size=200).items}
    expected = {(AS.value, "default"), (OR.value, "default"), (AS.value, STORE), (OR.value, ORCH), (CR.value, REGISTRY)}
    extra = {c for c in comps if c[1] != "default"} - expected
    assert not extra, f"extra components registered: {sorted(extra)}"
    connectors = {c.name for c in Client().list_service_connectors(size=100).items}
    assert connectors == {CONNECTOR}, f"connectors registered: {sorted(connectors)}"
