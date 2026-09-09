# zenml-bench

A public benchmark of tasks in which coding agents (Claude Code, Codex, OpenCode, Terminus 2, …) have to build, fix, configure and research with **real ZenML**, packaged in [Harbor](https://www.harborframework.com) task format so the same tasks run as an evaluation today and as a training environment (via verifiers / prime-rl) without rewriting them.

Status: early. Three build-and-fix tasks, one baseline. Design brief: `docs/2026-09-09-plan.md`. Decisions and resolved assumptions: `docs/decisions.md`. What baselines showed: `docs/findings.md`, `results/`.

## What a task looks like

Each task is a directory under `tasks/` in Harbor format: an `instruction.md` the agent reads, an `environment/Dockerfile` built on the shared base image (pinned ZenML, offline docs, agent CLIs), a reference `solution/solve.sh`, alternative valid solutions, deliberate shortcuts that must fail, and hidden `tests/` that grade **the state ZenML recorded** (runs, step statuses, artifacts, compiled configuration), never the agent's source text.

Every task must pass four checks before it counts: the reference solution passes five times out of five, doing nothing scores zero, every listed shortcut scores zero, and at least one different valid solution passes.

## Quick start

Requirements: Docker with a runtime that supports Harbor's network policies (OrbStack on macOS; Docker Desktop's VM does not), `uv`, and Harbor (`uv tool install harbor==0.22.0`).

```bash
# build the base image (ZenML pin lives in shared/base/Dockerfile)
docker build -t zenml-bench/base:0.96.4 shared/base

# run the reference solution for one task through Harbor
harbor run -p tasks/b3-stale-cache --agent oracle -o jobs --job-name b3-oracle

# run a real agent (keys in .env: ANTHROPIC_API_KEY, OPENAI_API_KEY)
harbor run -p tasks/b3-stale-cache --agent claude-code -m claude-opus-5 -k 3 -o jobs --job-name b3-claude --env-file .env

# the four verifier checks for a task
uv run scripts/verify_task.py tasks/b3-stale-cache

# harness × condition baseline matrix
uv run scripts/run_baselines.py tasks/b3-stale-cache --agent codex:gpt-5.6-terra --agent claude-code:claude-opus-5 --condition bare --condition skill -k 3 --env-file .env
```

For writing tasks, `scripts/grade_local.sh <task> [patch.sh]` runs a task's grader in a throwaway ZenML store without containers, in seconds. See `docs/task-authoring.md`.

## Tasks

| id | title | tier | what it tests |
|---|---|---|---|
| `b3-stale-cache` | stale cache | A | ZenML caches on a path string; make changed data invalidate the right steps without disabling caching |
| `b9-modernise-old-api` | modernise old API | A | a 0.4x-era project (`BaseParameters`, `Output`, `post_execution`) must run on the pinned ZenML with identical behaviour |
| `b7-kubernetes-settings` | Kubernetes settings | C | configure one step's pod (GPU, memory, node selector, service account) for a registered Kubernetes stack, graded by dry-run compile; no cluster |

Tiers: A = local store, no server; B = real ZenML server; C = Kubernetes configuration without a cluster; D = real Kubernetes execution (not in scope).

## License

Apache-2.0.
