# zenml-bench

A public benchmark of tasks in which coding agents (Claude Code, Codex, OpenCode, Terminus 2, …) have to build, fix, configure and research with **real ZenML**, packaged in [Harbor](https://www.harborframework.com) task format so the same tasks run as an evaluation today and as a training environment (via verifiers / prime-rl) without rewriting them.

Status: early. Build-and-fix tasks plus the first research-loop task (R1), all baselined with Claude Code and Codex at frontier and cheap tiers with Claude Code and Codex (all saturated at 12/12; see `results/`). Design brief: `docs/2026-09-09-plan.md`. Decisions and resolved assumptions: `docs/decisions.md`. What baselines showed: `docs/findings.md`, `results/`.

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
| `b5-custom-materializer` | custom materializer | A | a step returns a type with an unpicklable member; the instruction gives the symptom only; graded by loading the named artifact in a fresh process and scoring hidden data |
| `b7-kubernetes-settings` | Kubernetes settings | C | configure one step's pod (GPU, memory, node selector, service account) for a registered Kubernetes stack, graded by dry-run compile; no cluster |
| `b10-why-did-it-fail` | why did it fail? | A | a scheduled run failed among several distractor failures produced by real runs at image build; find the run, read the failed step's `exception_info`, fix the actual cause (thousands separators in one day's export), graded on hidden exports |
| `r1-improve-within-budget` | improve within a budget | A | research loop: at most 12 runs of the `research` pipeline, lower validation log loss, promote the best model version to `production`; graded by re-scoring the promoted, run-backed model artifact on hidden data (`gap_closed`, budget and evidence rules) |

Tiers: A = local store, no server; B = real ZenML server; C = Kubernetes configuration without a cluster; D = real Kubernetes execution (not in scope).

## License

Apache-2.0.
