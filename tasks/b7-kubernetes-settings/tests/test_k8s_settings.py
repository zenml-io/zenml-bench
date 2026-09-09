"""Grader for B7 kubernetes-settings (tier C1: grade the compiled configuration, no cluster).

1. `python run.py` completes on the local (active) stack.
2. The pipeline, built the way run.py builds it (config.yaml applied), is compiled against the registered
   `k8s-stack`; the effective per-step settings are read from the compiled deployment. Either form of
   GPU/memory (ResourceSettings or pod resources) is accepted; the Kubernetes orchestrator honours both.
Env: APP_DIR (default /app/k8s_training), FIXTURES_DIR unused.
"""
import importlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from zenml.client import Client
from zenml.config.compiler import Compiler
from zenml.config.pipeline_run_configuration import PipelineRunConfiguration
from zenml.enums import ExecutionStatus
from zenml.integrations.kubernetes.flavors import KubernetesOrchestratorSettings
from zenml.stack import Stack

APP_DIR = Path(os.environ.get("APP_DIR", "/app/k8s_training"))
STACK, ORCHESTRATOR, PIPELINE = "k8s-stack", "k8s", "training_pipeline"
STEPS = {"load_data", "split", "train", "evaluate"}
EIGHT_GI = {"8Gi", "8GiB", "8G", "8GB", "8gb", "8192Mi", "8192MiB", "8192M", "8192MB", 8589934592, "8589934592"}
ONE_GPU = {"1", 1, 1.0}


def compiled_deployment() -> Any:
    sys.path.insert(0, str(APP_DIR))
    os.chdir(APP_DIR)
    pipe = importlib.import_module("pipeline").training_pipeline
    cfg = APP_DIR / "config.yaml"
    run_config = PipelineRunConfiguration()
    if cfg.exists():
        matcher = list(PipelineRunConfiguration.model_fields)
        run_config = PipelineRunConfiguration(**pipe._parse_config_file(config_path=str(cfg), matcher=matcher))
        pipe = pipe.with_options(config_path=str(cfg))
    pipe.prepare()
    stack = Stack.from_model(Client().get_stack(STACK))
    return Compiler().compile(pipeline=pipe, stack=stack, run_configuration=run_config)


def k8s_settings(settings: dict[str, Any]) -> KubernetesOrchestratorSettings:
    raw = settings.get(f"orchestrator:{ORCHESTRATOR}") or settings.get("orchestrator.kubernetes") or settings.get("orchestrator")
    return KubernetesOrchestratorSettings.model_validate(raw.model_dump() if raw is not None else {})


def pod_resources(pod: dict[str, Any]) -> dict[str, Any]:
    res = pod.get("resources") or {}
    return {**(res.get("requests") or {}), **(res.get("limits") or {})}


def has_gpu_and_memory(step_cfg: Any) -> bool:
    rs = step_cfg.resource_settings
    pod = k8s_settings(step_cfg.settings).model_dump().get("pod_settings") or {}
    res = pod_resources(pod)
    gpu = rs.gpu_count == 1 or res.get("nvidia.com/gpu") in ONE_GPU
    mem = (rs.memory in EIGHT_GI) or (res.get("memory") in EIGHT_GI)
    return bool(gpu and mem)


def has_any_gpu(step_cfg: Any) -> bool:
    pod = k8s_settings(step_cfg.settings).model_dump().get("pod_settings") or {}
    return bool(step_cfg.resource_settings.gpu_count) or "nvidia.com/gpu" in pod_resources(pod)


@pytest.fixture(scope="module")
def local_run() -> Any:
    seen = {r.id for r in Client().list_pipeline_runs(size=500).items}
    proc = subprocess.run([sys.executable, "run.py"], cwd=APP_DIR, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"entrypoint failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    new = [r for r in Client().list_pipeline_runs(sort_by="desc:created", size=5).items if r.id not in seen]
    assert len(new) == 1
    return new[0]


@pytest.fixture(scope="module")
def deployment(local_run) -> Any:
    return compiled_deployment()


def test_local_run_still_completes(local_run):
    assert local_run.status == ExecutionStatus.COMPLETED
    assert local_run.pipeline.name == PIPELINE
    assert set(local_run.steps) == STEPS
    assert Client().active_stack_model.name == "default"


def step_service_account(settings: dict[str, Any]) -> str | None:
    """The service account the Kubernetes orchestrator would give this step's pod.

    ZenML resolves it as `step_pod_service_account_name or service_account_name` on the orchestrator settings
    (kubernetes_orchestrator_entrypoint.py). `KubernetesPodSettings` has NO service_account_name field: settings
    accept unknown keys silently, so `pod_settings.service_account_name` is a dead field and is NOT accepted.
    """
    ks = k8s_settings(settings).model_dump()
    return ks.get("step_pod_service_account_name") or ks.get("service_account_name")


def test_train_step_pod(deployment):
    train = deployment.step_configurations["train"].config
    pod = k8s_settings(train.settings).model_dump().get("pod_settings") or {}
    assert pod.get("node_selectors") == {"gpu": "true"}, f"node_selectors were {pod.get('node_selectors')}"
    assert step_service_account(train.settings) == "pipeline-runner", f"service account was {step_service_account(train.settings)}"
    assert has_gpu_and_memory(train), f"train GPU/memory not configured: resources={train.resource_settings} pod={pod}"


def test_other_steps_keep_defaults(deployment):
    for name, step in deployment.step_configurations.items():
        if name == "train":
            continue
        pod = k8s_settings(step.config.settings).model_dump().get("pod_settings") or {}
        assert not pod.get("node_selectors"), f"{name} has node selectors {pod.get('node_selectors')}"
        assert not step_service_account(step.config.settings), f"{name} has a service account"
        assert not has_any_gpu(step.config), f"{name} requests a GPU"


def test_orchestrator_pod_keeps_defaults(deployment):
    ks = k8s_settings(deployment.pipeline_configuration.settings).model_dump()
    orch = ks.get("orchestrator_pod_settings") or {}
    assert not orch.get("node_selectors"), f"orchestrator pod has node selectors {orch.get('node_selectors')}"
    assert not orch.get("service_account_name") and not ks.get("service_account_name"), "orchestrator pod service account changed"
    assert "nvidia.com/gpu" not in pod_resources(orch)


def test_collateral():
    stack = Client().get_stack(STACK)
    assert stack.components["orchestrator"][0].name == ORCHESTRATOR
    assert stack.components["orchestrator"][0].flavor_name == "kubernetes"
    assert {p.name for p in Client().list_pipelines(size=50).items} == {PIPELINE}
