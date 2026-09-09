The project in `/app/k8s_training` runs the ZenML pipeline `training_pipeline` (defined in `pipeline.py`; `run.py` applies `config.yaml` and runs it: `python run.py` from `/app/k8s_training`). The team has a Kubernetes stack registered as `k8s-stack` (orchestrator `k8s`); there is no cluster reachable from this machine, so do not try to run on it.

Configure the pipeline for `k8s-stack` so that, when it is run there:

1. the `train` step runs in a pod with one GPU (`nvidia.com/gpu`) and 8Gi of memory, on nodes labelled `gpu=true`, under the service account `pipeline-runner`;
2. the other steps and the orchestrator pod keep the defaults (no GPU, no node selector, default service account);
3. `python run.py` still completes on the current (local) stack, which must stay the active stack.

Keep the entrypoint, `pipeline.py` exposing `training_pipeline`, and the `config.yaml` mechanism. ZenML documentation is available offline at `/opt/zenml-docs/llms-full.txt`.
