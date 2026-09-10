# zenml-bench (verifiers v1 taskset)

### Overview
- **Environment ID**: `zenml-bench`
- **Short description**: coding agents build, fix, configure and do research loops with real ZenML 0.96.4; every task is graded on the state ZenML recorded (runs, step statuses, artifacts, compiled configuration, model version stages), never on the agent's source text.
- **Tags**: zenml, mlops, harbor, agentic, terminal, train, eval

### Datasets
- **Primary dataset**: the 18 Harbor tasks in https://github.com/zenml-io/zenml-bench (`tasks/`), listed in the repo's `registry.json`; Hub id `zenml/zenml-bench@0.1.0` once public.
- **Split sizes**: 18 eval tasks (v0.1). Generated training instances (`scripts/generate_instances.py`) are a separate, larger pool and are not in this taskset.

### Task
- **Type**: multi-turn, sandboxed terminal (Harbor task format: `instruction.md`, `environment/Dockerfile` on a pinned base image, hidden `tests/`).
- **Rubric**: each task's own frozen verifier writes `/logs/verifier/reward.json` with a binary `reward` and, for some tasks, extra metrics (`gap_closed`, `hidden_log_loss`, `agent_runs`, ...) that land in the trace's `metrics`. Every task passed the four checks: reference solution 5/5, doing nothing 0, every listed shortcut 0, at least one alternative solution 1.

### Images
verifiers never builds a task's `environment/Dockerfile`; it only pulls or reuses an image by name. Every zenml-bench task is Dockerfile-only (the Dockerfile copies the project in and seeds the ZenML store), so this taskset sets `ignore_dockerfile=True` and names one prebuilt image per task from `image_template`, default `zenml-bench/{task}:0.1.0`. Local docker runtime: build them with `scripts/build_task_images.sh` in the repo (needs the base image, `docker build -t zenml-bench/base:0.96.4 shared/base`). Prime sandboxes: push the 18 images to a registry and pass `--env.taskset.image-template "<registry>/{task}:0.1.0"`.

### Quickstart
```bash
uv pip install -e .                      # or: prime env install zenml/zenml-bench
uv run eval zenml-bench -m gpt-5.4-mini --client.base-url https://api.openai.com/v1 --client.api-key-var OPENAI_API_KEY \
  --env.agent.harness.id codex --env.agent.runtime.type docker --no-push
```
`eval` is verifiers' v1 runner (`vf-eval` is the legacy one and cannot load a v1 taskset). Outputs: `outputs/<run>/traces.jsonl` + `configs/resolved/eval.json`. The taskset resolves the dataset from the repo's `registry.json` at tag `v0.1` (Harbor's `--repo` route), so it works before the Harbor Hub entry is public. `ignore_timeouts=false` (the default here) keeps the task-authored budgets; the research tasks state their wall-clock budget in the instruction.

### Environment arguments
| arg | default | description |
|---|---|---|
| `dataset` | `zenml-bench@0.1.0` | Harbor dataset id (bare name with `repo`/`registry_path`; `org/name@ref` on the Hub) |
| `repo` | `zenml-io/zenml-bench@v0.1` | git registry to resolve from; set `None` once the Hub id is used |
| `image_template` | `zenml-bench/{task}:0.1.0` | prebuilt image per task (`{task}` = task directory name) |
| `tasks` | all | subset of task names |
| `timeout_multiplier` | 1.0 | scale agent/verifier timeouts |
