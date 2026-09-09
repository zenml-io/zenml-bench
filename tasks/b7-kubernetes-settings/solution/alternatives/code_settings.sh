#!/usr/bin/env bash
# Alternative: settings on the step decorator in code, resources expressed inside the pod spec.
set -euo pipefail
cd "${APP_DIR:-/app/k8s_training}"
python - <<'PY'
from pathlib import Path
p = Path("steps.py"); s = p.read_text()
old = "@step\ndef train("
assert old in s
s = s.replace("from zenml import step", """from zenml import step
from zenml.integrations.kubernetes.flavors import KubernetesOrchestratorSettings
from zenml.integrations.kubernetes.pod_settings import KubernetesPodSettings

TRAIN_K8S = KubernetesOrchestratorSettings(
    step_pod_service_account_name="pipeline-runner",
    pod_settings=KubernetesPodSettings(
        node_selectors={"gpu": "true"},
        resources={"requests": {"nvidia.com/gpu": "1", "memory": "8Gi"}, "limits": {"nvidia.com/gpu": "1", "memory": "8Gi"}},
    )
)""")
s = s.replace(old, '@step(settings={"orchestrator.kubernetes": TRAIN_K8S})\ndef train(')
p.write_text(s)
PY
