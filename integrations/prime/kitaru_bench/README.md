# kitaru-bench (verifiers v1 taskset)

### Overview
- **Environment ID**: `kitaru-bench`
- **Short description**: coding agents use real Kitaru 0.27.7 on recorded agent histories: apply and repair checks, find the conversations a problem affected, import traces from other tools, replay a recorded run with a fix, and set an agent up to be recorded. Every task is graded on what Kitaru recorded, never on what the agent says it did.
- **Tags**: kitaru, agents, evals, tracing, harbor, agentic, terminal, train, eval

### Datasets
- **Primary dataset**: the 37 Harbor tasks in https://github.com/zenml-io/zenml-bench (`kitaru/tasks/`), listed in the repo's `registry.json` as `kitaru-bench`; Hub id `zenml/kitaru-bench@0.1.0` once public.
- **Split sizes**: 37 eval tasks (v0.1) on five fictional companies.

### Task
- **Type**: multi-turn, sandboxed terminal (Harbor task format: `instruction.md`, `environment/Dockerfile` on a pinned base image, hidden `tests/`).
- **Rubric**: each task's own verifier writes `/logs/verifier/reward.json` with a binary `reward`; most also write the separate criteria to `metrics.json`. Every task passed four checks: reference solution 5/5, doing nothing 0, every listed shortcut 0, a second valid solution 1.

### Images
verifiers never builds a task's `environment/Dockerfile`; it only pulls or reuses an image by name. Each task's Dockerfile loads a recorded history into Kitaru's database, so this taskset sets `ignore_dockerfile=True` and names one prebuilt image per task from `image_template`, default `zenmldocker/kitaru-bench-tasks:{task}-0.1.0`. To build them locally under the same names: `kitaru/scripts/build_task_images.sh` in the repo.

From each task, verifiers takes the health check (it starts PostgreSQL, the Kitaru server and a worker before the agent), the agent's Unix user (`agent`, not root) and the network allow-list. A runtime that cannot switch user is rejected.

### Quickstart
```bash
uv pip install -e .                      # or: prime env install zenml/kitaru-bench
uv run vf-run kitaru-bench -m gpt-5.6-terra --client.base-url https://api.openai.com/v1 --client.api-key-var OPENAI_API_KEY \
  --env.agent.harness.id codex --env.agent.runtime.type docker
```
Outputs: `outputs/<run>/traces.jsonl` and `configs/resolved/run.json`. `uv run vf-validate kitaru-bench --runtime.type docker` runs every task with no agent and expects a reward of 0.

### Environment arguments
| arg | default | description |
|---|---|---|
| `dataset` | `kitaru-bench@0.1.0` | Harbor dataset id (bare name with `repo`/`registry_path`; `org/name@ref` on the Hub) |
| `repo` | `zenml-io/zenml-bench@kitaru-v0.1` | git registry to resolve from; set `None` once the Hub id is used |
| `image_template` | `zenmldocker/kitaru-bench-tasks:{task}-0.1.0` | prebuilt image per task (`{task}` = task directory name) |
| `tasks` | all | subset of task names |
| `timeout_multiplier` | 1.0 | scale agent and verifier timeouts |

### Metrics
| metric | meaning |
|---|---|
| `reward` | 1 if the task's verifier accepted what Kitaru recorded, else 0 |
