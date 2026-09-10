# zenml-bench

A public benchmark of tasks in which coding agents (Claude Code, Codex, OpenCode, Terminus 2, …) have to build, fix, configure and research with **real ZenML**, packaged in [Harbor](https://www.harborframework.com) task format so the same tasks run as an evaluation today and as a training environment (via verifiers / prime-rl) without rewriting them.

Status: early. Eighteen tasks (build-and-fix, research loops, and a no-framework comparison variant), each verified with the four checks and baselined with Claude Code and Codex at frontier and cheap tiers; per-task pass rates, cost and difficulty are in the generated [Results](#results) table. Design brief: `docs/2026-09-09-plan.md`. Decisions and resolved assumptions: `docs/decisions.md`. What baselines showed: `docs/findings.md`, `results/`.

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

# the "+ MCP" condition: the ZenML MCP server (baked into the base image) reading the container's local store
uv run scripts/run_baselines.py tasks/b10-why-did-it-fail --agent claude-code:claude-opus-5 --condition mcp -k 3 -n 2 --env-file .env
# or directly: harbor run ... --mcp-config shared/mcp/zenml.json

# a small open model through OpenRouter on Harbor's Terminus 2 harness (OPENROUTER_API_KEY in .env; the model is
# called from the host, so the task's network policy does not apply). --ak passes Terminus 2 constructor kwargs.
uv run scripts/run_baselines.py tasks/b4-nondeterministic-step --agent terminus-2:openrouter/qwen/qwen3.5-9b -k 5 -n 2 \
    --job-prefix small --name-with-model --ak max_turns=40 --ak record_terminal_session=false --env-file .env
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
| `b14-artifact-retrieval` | artifact retrieval | A | among a fortnight of runs (scheduled, manual, backfill; some failed), find the completed backfill run with the largest total and build a one-step pipeline whose recorded input is that run's summary artifact version; graded on step-input lineage |
| `b10h-why-did-it-fail-hard` | why did it fail? (hard) | A | as B10, but the instruction never says how scheduled runs are recorded, the failed days' exports are quarantined off the box (the recorded traceback or the `load` step's output artifact is the evidence), and a second scheduled failure on another day is also a code fault; graded on the restored export and hidden ones |
| `b11-stack-registration` | stack registration | A/C | register an S3 artifact store behind a placeholder AWS service connector, a Kubernetes orchestrator and a container registry into a stack, make it the project's active stack, keep `default` intact; no route to AWS, so the connector and the link must be made without verification; graded on the recorded components, the connector link, the per-repository active stack and a run on `default` |
| `b4-nondeterministic-step` | nondeterministic step | A | a random sampling step is served from the cache; make it draw a fresh sample every run while the expensive loader upstream keeps caching; graded on two grader runs with an unseen `n` (loader CACHED, sampler executed, samples differ, report matches its own run) |
| `b6-model-promotion` | model promotion | A | two registered versions with a recorded metric; promote the better one to `production` and make inference follow the stage; the grader re-promotes the other version and reruns on the same hidden batch, which catches version numbers and the cached `predict` (the model version is not in ZenML's cache key) |
| `b2-script-to-pipeline` | script to pipeline | A | a plain prepare/train/evaluate script becomes the named pipeline `credit_training` with typed steps; graded by rerunning the entrypoint on the visible and a hidden file and comparing the recorded `accuracy` artifact with the original script's output, plus step wiring (evaluate takes the `model` artifact as input) |
| `b1-source-root-repair` | source-root repair | A | a stray `.zen` in a subdirectory makes ZenML record step sources against the wrong root (`run.load_history`) and the daily entrypoint cannot import `src/`; fix the repository root so both entrypoints run and every recorded source imports from the project root, leaving the neighbouring project untouched (file hashes, its `.zen`, its run) |
| `b14h-artifact-retrieval-hard` | artifact retrieval (hard) | A | as B14, but three backfill days were re-processed with corrected exports (one re-processing failed), the criterion is a business rule with supersession, and the report must cite the artifact's ZenML name and version; every simpler rule picks a different run |
| `r1-improve-within-budget` | improve within a budget | A | research loop: at most 12 runs of the `research` pipeline, lower validation log loss, promote the best model version to `production`; graded by re-scoring the promoted, run-backed model artifact on hidden data (`gap_closed`, budget and evidence rules) |
| `r2-screen-then-confirm` | screen, then confirm | A | as R1, but the promotion counts only if the production version is backed by three completed runs on distinct seeds whose mean recorded loss beats a stated threshold; single-seed promotion scores 0 |
| `r1-bare-improve-within-budget` | improve within a budget (no framework) | A | the same problem in a `prepare.py` / `train.py` / `results.tsv` repo with no ZenML; promotion is a file copy tied to a results row by hash; the with/without-ZenML comparison |
| `r1-clock-improve-within-budget` | improve within a budget (25-minute clock) | A | R1 with one extra rule: the agent is told it has 25 minutes and 2 CPUs, and Harbor enforces both (`timeout_sec`, `cpus`); same project, data and grader as R1. Built for the with/without-ZenML comparison (`results/level3-comparison.md`) |
| `r1-bare-clock-improve-within-budget` | improve within a budget (no framework, 25-minute clock) | A | R1-bare with the same clock rule; the pair differs from R1-clock only in ZenML being present |

Tiers: A = local store, no server; B = real ZenML server; C = Kubernetes configuration without a cluster; D = real Kubernetes execution (not in scope).

## Results

<!-- results:start -->
| task | tier | opus-5 | gpt-5.6-terra | haiku-4.5 | gpt-5.4-mini | median cost | band |
|---|---|---|---|---|---|---|---|
| `b1-source-root-repair` | A | 3/3 | 3/3 | – | – | $0.50 | saturated |
| `b10-why-did-it-fail` | A | 3/3 | 3/3 | 3/3 | 3/3 | $0.17 | saturated |
| `b10h-why-did-it-fail-hard` | A | 3/3 | 3/3 | 1/3 | 3/3 | $0.34 | headroom (haiku-4.5) |
| `b11-stack-registration` | A/C | 3/3 | 3/3 | – | – | $0.39 | saturated |
| `b14-artifact-retrieval` | A | 3/3 | 3/3 | – | – | $0.24 | saturated |
| `b14h-artifact-retrieval-hard` | A | 3/3 | 3/3 | 1/3 | 3/3 | $0.40 | headroom (haiku-4.5) |
| `b2-script-to-pipeline` | A | 3/3 | 3/3 | – | – | $0.38 | saturated |
| `b3-stale-cache` | A | 3/3 | 3/3 | 1/3 | 3/3 | $0.27 | headroom (haiku-4.5) |
| `b4-nondeterministic-step` | A | 3/3 | 3/3 | – | – | $0.27 | saturated |
| `b5-custom-materializer` | A | 3/3 | 3/3 | 3/3 | 3/3 | $0.20 | saturated |
| `b6-model-promotion` | A | 3/3 | 3/3 | – | – | $0.25 | saturated |
| `b7-kubernetes-settings` | C | 3/3 | 3/3 | 0/3 | 2/3 | $0.40 | headroom (gpt-5.4-mini) |
| `b9-modernise-old-api` | A | 3/3 | 3/3 | 3/3 | 3/3 | $0.40 | saturated |
| `r1-bare-clock-improve-within-budget` | A | 5/5 | 5/5 | – | – | $0.41 | saturated |
| `r1-bare-improve-within-budget` | A | 1/6 | 3/3 | – | – | $1.22 | mixed |
| `r1-clock-improve-within-budget` | A | 5/5 | 5/5 | – | – | $0.78 | saturated |
| `r1-improve-within-budget` | A | 3/3 | 3/3 | 3/3 | 3/3 | $0.33 | saturated |
| `r2-screen-then-confirm` | A | 3/5 | 3/3 | – | – | $1.02 | headroom (opus-5) |

Bare condition only (no skill, no MCP), 169 trials, pass counts as passed/attempted per model. Three attempts per cell is a small sample: 3/3 against 2/3 is not a meaningful gap. Cost is the harness's own figure per trial at the prices of the run date, median over all bare trials of the task. Band: *saturated* = every model ≥ 80 %, *headroom* = a model sits in the 20–80 % band where a benchmark ranks agents and a trainer gets signal, *floor* = every model < 20 %. Per-condition tables, trajectories read by hand and what tripped each agent are in the `results/*.md` pages. Regenerate with `uv run scripts/results_table.py`.
<!-- results:end -->

## License

MIT.
