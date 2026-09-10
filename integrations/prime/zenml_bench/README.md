# zenml-bench (verifiers v1 taskset)

### Overview
- **Environment ID**: `zenml-bench`
- **Short description**: coding agents build, fix, configure and do research loops with real ZenML 0.96.4; every task is graded on the state ZenML recorded (runs, step statuses, artifacts, compiled configuration, model version stages), never on the agent's source text.
- **Tags**: zenml, mlops, harbor, agentic, terminal, train, eval

### Datasets
- **Primary dataset**: the 18 Harbor tasks in https://github.com/strickvl/zenml-bench (`tasks/`), listed in the repo's `registry.json`; Hub id `zenml/zenml-bench@0.1.0` once published.
- **Split sizes**: 18 eval tasks (v0.1). Generated training instances (`scripts/generate_instances.py`) are a separate, larger pool and are not in this taskset.

### Task
- **Type**: multi-turn, sandboxed terminal (Harbor task format: `instruction.md`, `environment/Dockerfile` on a pinned base image, hidden `tests/`).
- **Rubric**: each task's own frozen verifier writes `/logs/verifier/reward.json` with a binary `reward` and, for some tasks, extra metrics (`gap_closed`, `hidden_log_loss`, `agent_runs`, ...). Every task passed the four checks: reference solution 5/5, doing nothing 0, every listed shortcut 0, at least one alternative solution 1.

### Quickstart
```bash
uv pip install -e .                      # or: prime env install zenml-bench (after it is pushed)
uv run vf-eval zenml-bench -m <model>    # uses the taskset's harness defaults
```
The taskset resolves the dataset from the repo's `registry.json` at tag `v0.1` (Harbor's `--repo` route), so it works before the Harbor Hub entry exists. Set `ignore_timeouts=false` (the default here) to keep the task-authored budgets; the research tasks state their wall-clock budget in the instruction.

### Environment arguments
| arg | default | description |
|---|---|---|
| `dataset` | `zenml-bench@0.1.0` | Harbor dataset id (bare name with `repo`/`registry_path`; `org/name@ref` on the Hub) |
| `repo` | `strickvl/zenml-bench@v0.1` | git registry to resolve from; set `None` once the Hub id is used |
| `tasks` | all | subset of task names |
| `timeout_multiplier` | 1.0 | scale agent/verifier timeouts |
