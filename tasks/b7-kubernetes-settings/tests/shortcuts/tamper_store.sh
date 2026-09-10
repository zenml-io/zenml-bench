#!/usr/bin/env bash
# Tamper: put the pod settings on the registered `k8s` orchestrator's row in SQLite (its configuration JSON) and
# change nothing in the project. Component configuration is not where per-step settings live, so the compiled
# deployment carries none of it. Must score 0.
set -euo pipefail
cd "${APP_DIR:-/app/k8s_training}"
python - <<'PY'
import base64, json, sqlite3
from zenml.client import Client
zs = Client().zen_store
con = sqlite3.connect(zs.config.url.removeprefix("sqlite:///"))
(raw,) = con.execute("select configuration from stack_component where name='k8s' and type='orchestrator'").fetchone()
cfg = json.loads(base64.b64decode(raw))
cfg.update({"pod_settings": {"node_selectors": {"gpu": "true"}, "resources": {"limits": {"nvidia.com/gpu": "1", "memory": "8Gi"}}}, "step_pod_service_account_name": "pipeline-runner"})
con.execute("update stack_component set configuration=? where name='k8s' and type='orchestrator'", (base64.b64encode(json.dumps(cfg).encode()),))
con.commit(); con.close()
PY
