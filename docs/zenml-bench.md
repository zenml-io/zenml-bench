# ZenML Bench: what we run, and why it's hard

*Last checked against the repository: 2026-11-23 (ZenML 0.96.4, task set v0.1). Pass rates are not on this page; they are generated into the [`README.md` results table](../README.md#results).*

Each task is a small, working ZenML project with one thing wrong, or one job left undone: a cache that serves stale data, a pipeline written for a five-year-old API, a scheduled run that failed among several that failed for other reasons. A coding agent gets the project and a one-paragraph instruction. A hidden grader scores 1 or 0 by reading what ZenML recorded (runs, step statuses, artifacts, model versions, compiled settings) and by re-running the agent's code on data it never saw.

This page covers every project and every task. The sister page for the Kitaru set is [`kitaru-bench.md`](kitaru-bench.md). How to write a task is in [`task-authoring.md`](task-authoring.md).

## The short version

| | count | what it means |
|---|---|---|
| tasks | 18 | 13 build-and-fix tasks (B), 3 research-loop tasks (R1, R2, R1-clock), 2 no-framework twins (R1-bare, R1-bare-clock) |
| projects | 11 | working example projects under `shared/projects/`, each copied into the tasks that use it |
| conditions | 3 | the same agent with nothing extra (`bare`), with ZenML's written skills (`skill`), or with the ZenML MCP server (`mcp`) |
| generated families | 2 | `b10` and `b3`: a script turns one verified task into as many varied instances as you want; seeds 0–4 of each are committed as a held-out set |

- **What makes a task hard is ZenML's real behaviour, not trick questions.** The cache key includes a file *path*, not its contents. A model version is not part of the cache key. `zenml stack set` outside a project changes the global stack, not the project's. Several tasks have an obvious fix that makes the run go green and still scores 0, because ZenML recorded something different from what the agent thinks it did.
- **History is real, not mocked.** Where a task needs past runs (B1, B6, B10, B10H, B14, B14H), the image build runs the real pipeline several times, with real failures, so the store holds exactly what ZenML would record.
- **Every grader assumes the store was forged.** The store is a writable SQLite file in the same container as the agent. So each non-research task ships a `tamper_store.sh` shortcut that hand-writes the "right" rows and must score 0, and graders check that the runs they read were genuinely produced by ZenML.

## How a run works

![How one ZenML Bench attempt runs: image build, agent, grader, store, reward](charts/zb-how-a-run-works.svg)

The container:

- **No server.** ZenML uses its default local SQLite store inside the container. Tier A tasks need nothing else. Tier C tasks (B7, part of B11) register a Kubernetes stack with no cluster behind it and are graded by compiling the pipeline without running it.
- **Network.** The image build and the grader run with no network. The agent may reach only `api.anthropic.com`, `api.openai.com` and `chatgpt.com`. These policies need OrbStack (or Linux); Docker Desktop rejects them. Terminus 2 calls its model from the host, so the policy does not apply to it.
- **Docs offline.** `/opt/zenml-docs/llms-full.txt` holds ZenML's documentation as one file. Every instruction ends by pointing to it.
- **Time.** 30 minutes for B tasks, 40 for R1, R2 and R1-bare, 25 for the two clock tasks (which also get 2 CPUs).

The three conditions add one thing each, and the task directories stay the same:

| condition | what the agent gets | how |
|---|---|---|
| `bare` | the container and the offline docs | default |
| `skill` | ZenML's pipeline-authoring and quick-wins skills from `zenml-io/skills`, pinned by SHA | `harbor run --skill <dir>` (set by `scripts/run_baselines.py`) |
| `mcp` | the ZenML MCP server, started by the agent CLI over stdio, reading the container's own store | `harbor run --mcp-config shared/mcp/zenml.json` |

### Four checks before a task counts

1. The reference solution scores 1, five times out of five.
2. Doing nothing scores 0.
3. Every shortcut in `tests/shortcuts/` scores 0. Shortcuts are the tempting wrong fixes: "turn caching off everywhere", "hard-code the score", "forge the run".
4. A second, different valid solution scores 1. Most tasks also have `solve_then_run_twice.sh`, because a real agent keeps running the pipeline after it has fixed it, and that can fill the cache in ways the oracle never does.

### How graders refuse a forged store

> **Why this matters.** An agent being trained with reinforcement learning will take the shortest path to reward 1. If that path is "write a completed run into SQLite", it will find it. So graders never trust a row just because it is there.

`shared/checks/store_integrity.py` provides `assert_genuine_run(run)`. For every step of a graded run:

- **A completed step** must have a cache key, and each of its outputs must be a real step output produced by that same step, with the file present on disk.
- **A cached step** must point at an original completed step in a *different* run, with the same cache key and the *same artifact versions*.

On top of that, most graders run the agent's entrypoint themselves on a fixture the agent never saw, find the run they just created by comparing run ids before and after, and grade that run.

## Projects and their tasks

### Caching: `nightly` (B3) and `sampling` (B4)

**`nightly`**, pipeline `nightly_training(path)`. The training step sleeps for 3 seconds to stand in for something expensive.

![nightly pipeline: load_data, train, evaluate](charts/zb-nightly.svg)

The fault: ZenML builds `load_data`'s cache key from its code and its parameters. The parameter is the path *string*. Replace the file at that path and the key does not change, so the step is served from the cache with the old data.

![B3 grading: five runs with fixtures a a b b c, a correct fix against the obvious fix](charts/zb-b3-grading.svg)

**`sampling`**, pipeline `qa_sampling(n)`. 20,000 synthetic payment events.

![sampling pipeline: load_events, sample_events, review_report](charts/zb-sampling.svg)

The fault is the opposite: the sampler should be random every run, but ZenML caches it, so every QA review gets the same 50 events.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `b3-stale-cache` | make changed data rerun the steps that read it, while an unchanged rerun keeps `train` cached; caching must stay on | the obvious fix, `enable_cache=False` on `load_data`, fails: each fresh DataFrame is a new artifact, so `train` reruns every time. A working fix gives ZenML a content hash of the file (an extra small step, a `cache_func`, or `file_dependencies`) | the grader swaps fixtures a, a, b, b, c and runs each: scores right, `train` executed on runs 3 and 5 and cached on 2 and 4 |
| `b4-nondeterministic-step` | the sampler must draw a fresh sample every run while the expensive loader keeps caching | `CachePolicy(expires_after=0)` looks like "expire now" but 0 means "not set", so the step stays cached; switching caching off on the loader or the report is also wrong | two grader runs with an `n` the agent never saw: loader cached, sampler executed, samples differ, each report matches its own sample |

### Old API: `legacy_training` (B9) and its modern twin `k8s_training` (B7)

Both projects are the same four-step training pipeline. `legacy_training` is written in the ZenML 0.4x API on purpose (`BaseParameters`, `Output(...)` annotations, `post_execution`).

![training pipeline: load_data, split, train, evaluate](charts/zb-training.svg)

For B7 the image registers a Kubernetes orchestrator `k8s` (context `zenml-prod`, namespace `ml-training`), a container registry and a stack `k8s-stack`. There is no cluster; `default` stays the active stack.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `b9-modernise-old-api` | make the 0.4x project run on 0.96.4 with identical behaviour: same pipeline name, steps, output names, recorded parameters and score | unlearning an old mental model; a step that returns a tuple without a `Tuple` annotation is one output, not four; running a step alone registers an extra pipeline | runs on the image's data and on unseen data: steps, output names, parameter values in the step config, the score |
| `b7-kubernetes-settings` | give the `train` step's pod 1 GPU, 8Gi memory, node selector `gpu=true` and service account `pipeline-runner`, for `k8s-stack` only; everything else keeps defaults | the details are spread across several docs pages; `pod_settings.service_account_name` looks right but is not a field, and ZenML accepts it silently; the top-level `service_account_name` also changes the orchestrator's pod | a local run on `default`, then a dry-run compile against `k8s-stack` that reads each step's compiled settings |

### Artifacts: `churn_scoring` (B5) and `credit_script` (B2)

**`churn_scoring`**, pipeline `churn_training()`: `load_data → train → evaluate`. `train` returns a `ChurnScorer` that holds an in-memory `sqlite3` table of segment adjustments. `serve.py` loads the artifact `churn_scorer` in a new process.

**`credit_script`** is not a pipeline yet: a plain `train.py` with `prepare`, `train` and `evaluate` functions on 2,400 synthetic credit rows.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `b5-custom-materializer` | symptom only, `TypeError: cannot pickle 'sqlite3.Connection'`: make the run complete and store the scorer as `churn_scorer`, so `serve.py` gives the same scores in a fresh process | the fix must keep features, threshold and the SQLite calibration; saving a bare model, or a materializer that guesses the threshold, runs green and scores wrong | the grader's run must output `churn_scorer`; a fresh interpreter loads it and scores hidden data within 1e-6 |
| `b2-script-to-pipeline` | turn the script into pipeline `credit_training` with at least three typed steps and artifacts named `model` and `accuracy` | `prepare` returns `train_test_split(...)` directly, which a `Tuple`-annotated step treats as one output (the same trap as B9); an `evaluate` that retrains gets the right number without using the `model` artifact | the entrypoint on the visible and a hidden 900-row file: accuracy equals the original script's, and `evaluate` takes `model` as input |

### Run history: `daily_report` (B10, B14, B14H) and `daily_report_hard` (B10H)

A daily regional sales report. Pipeline `daily_report(date)`:

![daily_report pipeline: load, parse, summarise, write_report](charts/zb-daily-report.svg)

`python run.py --date D --trigger scheduled` names the run `scheduled-D` and tags it `scheduled`. A run started by hand is named `manual-D-<time>` and tagged `manual`. In `daily_report_hard`, `load` is never cached, `summarise` rejects rows from unknown regions, and `bin/nightly.sh` is the cron job that starts scheduled runs.

**B10's history.** The image build runs the pipeline six times. Most runs fail, and only one failure is a code fault:

![B10 seeded runs by day](charts/zb-b10-history.svg)

The most recent *failed* run is the hand-started typo, not the scheduled run the instruction means. The real cause sits in the 09-09 run's `parse` step `exception_info`: amounts of 1,000 or more were written as `"1,234.50"`.

**B10H's history** has ten runs. On top of B10's pattern, an old manual run for 08-30 fails on ISO `T` timestamps, and the scheduled run for 09-03 fails in `summarise` on regions spelled `"North"` and `"west "`. Both failed days' exports (09-03 and 09-09) are then moved off the box, so the agent can only read the cause from the recorded traceback or from the `load` step's output artifact.

![B10H seeded runs by day](charts/zb-b10h-history.svg)

**B14's and B14H's history** adds hand-run backfill days before the scheduled ones. All of them were tagged `backfill` after the fact.

![B14 seeded runs by day](charts/zb-b14-history.svg)

B14H then re-processes three backfill days with corrected exports. The rule is "the most recent processing of a day that *completed* counts for that day". Each simpler rule picks a different run, which is the point:

![B14H seeded runs: first processing, re-processing and scheduled](charts/zb-b14h-history.svg)

| rule the agent might use | run it picks | right? |
|---|---|---|
| largest summary, any status | 08-26 first processing (failed) | no |
| largest completed, ignoring re-processing | 08-27 first processing (superseded by its v2) | no |
| latest processing, any status | 08-25 v2 (failed, so 08-25's first run still counts) | no |
| largest of every completed run, not only backfills | scheduled 09-08 | no |
| supersession rule, then largest day | **08-26 v2** (`daily_report::summarise::output` version 5) | yes |

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `b10-why-did-it-fail` | the most recent scheduled run failed: find the day and cause, fix the code so that day counts every row, run it | distractor failures in `load` and `write_report`, and a more recent manual failure; dropping or coercing the bad rows runs green and loses money from the totals | a completed, genuine 09-09 run with the right summary, then two hidden exports (with and without separators); seeded runs and data untouched |
| `b10h-why-did-it-fail-hard` | as B10, without being told how scheduled runs are named, with the export quarantined, and with every *code-preventable* scheduled failure of the week fixed | a blind rerun of 09-09 fails with a different error (the file is gone); the second code fault on 09-03 means fixing only this morning's cause scores 0; adding `"North"` to the allowed regions is a patch, not a fix | runs for every day on disk, the restored 09-09 export, four hidden exports (plain, separators, odd regions, both) |
| `b14-artifact-retrieval` | find the completed backfill run with the largest total; build a one-step `region_report` pipeline whose recorded input is that run's summary artifact | a failed backfill holds the largest summary; a scheduled run beats every backfill day; recomputing from the CSV gets the number without the lineage | the step's recorded input artifact, the report, then the grader saves an unseen summary and runs `region_report.py <id>` |
| `b14h-artifact-retrieval-hard` | as B14 with re-processed days and the supersession rule; the report cites the artifact's ZenML name and version | every simpler rule picks a different run (table above) | as B14, plus the cited name and version |

### Model versions: `model_promotion` (B6)

Two pipelines share the model `demand_forecaster`:

![model_promotion: training and inference pipelines](charts/zb-model-promotion.svg)

The image trains version 1 (linear, the better one), then version 2 (random forest, worse), then runs inference once, which reads "latest", that is, version 2.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `b6-model-promotion` | promote the version with the lowest `val_mae` to `production`, and make inference follow the stage from now on | the model version is not in ZenML's cache key: switch to `Model(version="production")` and `predict` is still served from the cache, linked to the new version while its predictions come from the old one | production is the better version; then the grader promotes the *other* version and reruns on the same hidden batch: the link and the predictions must follow |

### Repository roots: `analytics_workspace` (B1)

The workspace root is `/app`. Inside it, `analytics/` holds two entrypoints (a daily job and a backfill job in `jobs/backfill/`) that share `src/features.py`. `legacy_reports/` is a neighbouring project with its own `.zen` and one recorded run, and it must not be touched.

ZenML finds its repository by walking up from the current directory to the nearest `.zen` folder, and records every step's source relative to that root. The image build puts a stray `.zen` inside `analytics/jobs/backfill/`, so the backfill's steps are recorded as `run.load_history` instead of `jobs.backfill.run.load_history`.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `b1-source-root-repair` | make both entrypoints run with the repository root at `/app/analytics`, leaving `/app/legacy_reports` exactly as it is | fixing the import with `sys.path` alone leaves the roots wrong; `zenml init` at `/app` moves the neighbour's root too; keeping the stray `.zen` means the backfill still finds it first | the grader runs both entrypoints: every recorded source imports from `/app/analytics`, `.zen` only there, the neighbour's file hashes, `.zen` and run unchanged |

### Stacks: `stack_onboarding` (B11)

A two-step smoke-check pipeline with no data. The task is the stack, not the pipeline.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `b11-stack-registration` | register an AWS service connector, an S3 artifact store linked through it, a Kubernetes orchestrator and a container registry, assemble stack `prod-k8s` and make it active *for this project*, keeping `default` intact | there is no route to AWS: `artifact-store register --connector` always verifies, prints an error when that fails and leaves the store unlinked; `zenml stack set` outside the project changes the global stack, not the project's | the recorded components, the connector link and bucket, the project's active stack, and a run on `default` |

### Research loops: `research` (R1, R2, R1-clock) and `research_bare` (R1-bare, R1-bare-clock)

A small binary classification problem. Pipeline `research(config, seed)`; every run is attached to the model `research_model`, with the version named after the config.

![The chain the R1 and R2 grader walks](charts/zb-research-chain.svg)

> **"A link is not evidence."** ZenML lets you attach any artifact to any model version. So the grader does not trust the link. It walks a chain: the `production` version → a linked run of `research` that completed → that run's `train` step → the `model` output that step produced. Only a model that survives the chain is scored, by the grader's own evaluator on hidden data. The step also records how many rows it trained on and a digest of them, so "train on the full set" is visible in the record.

`gap_closed` measures how far the agent got from the baseline (logistic regression, hidden log loss 0.6585) towards a reference (gradient boosting, 0.4581). 0.5 means halfway.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `r1-improve-within-budget` | at most 12 runs; lower validation loss; promote the best version to `production` | promoting a hand-saved model, training on the full set, or editing the evaluation all look like success | `gap_closed ≥ 0.5` on hidden data through the chain, within budget, on the seed's slice |
| `r2-screen-then-confirm` | as R1, but the production version needs 3 completed runs on 3 different seeds with mean loss ≤ 0.56 | running the same seed three times gives cache hits, not evidence; a single good seed is luck | R1's checks plus the evidence rule |
| `r1-clock-improve-within-budget` | R1 with a stated 25-minute clock and 2 CPUs, enforced by Harbor | the clock binds where the run budget doesn't: tool-call latency is the agent's real cost | as R1 |
| `r1-bare-improve-within-budget` | the same problem with no framework: `train.py` appends to `results.tsv` and saves a pickle; promotion is copying a file to `best_model.pkl` | the agent keeps its own lab notebook; deleting rows to hide extra runs is caught | `best_model.pkl` tied to a results row by sha256, then the same hidden-data scoring |
| `r1-bare-clock-improve-within-budget` | R1-bare with the same clock | the twin of R1-clock: the pair differs only in ZenML being present | as R1-bare |

The with-and-without-ZenML comparison these twins were built for is written up in `results/level3-comparison.md`.

## Generated instances

`scripts/generate_instances.py <family> --n N --seed S --out <dir>` turns one verified task into many. It varies surface details and the fault, runs the reference through ZenML in a throwaway store to compute expected values, and checks that the unfixed project fails the way the instance says it does. Seeds 0–4 of each family are committed under `tasks/generated/` as a held-out set; training sets use seeds from 1000 up in the gitignored `tasks/generated-train/`.

| family | from | what changes per instance |
|---|---|---|
| `b10` | B10 | month and days, region names, the fault (thousands separators, region spelling, slashed dates, negative amounts in brackets, a new column), which distractor failures appear, the run naming and tag scheme, the pipeline name |
| `b3` | B3 | pipeline, step and output names, the data path, whether the path is a parameter, which step is expensive (trainer or evaluator), data size and noise |

The committed `b10` held-out instances use the date-format, bracketed-negative and separator faults; none uses the region or new-column faults.

## Where things live

| what | where |
|---|---|
| base image (ZenML pin, agent CLIs, docs, MCP server) | `shared/base/Dockerfile` |
| a project | `shared/projects/<project>/`; copied into tasks with `scripts/sync_project.sh` |
| a task | `tasks/<id>/` (`instruction.md`, `task.toml`, `environment/`, `solution/`, `tests/`) |
| forged-store check | `shared/checks/store_integrity.py`; copied into tasks by `scripts/sync_checks.sh` |
| the four checks through Harbor | `scripts/verify_task.py <task>`; fast local loop: `scripts/grade_local.sh <task> [patch.sh]` |
| baselines and the README table | `scripts/run_baselines.py`, `scripts/results_table.py`, `results/` |
| why things are the way they are | `docs/decisions.md`, `docs/findings.md` |
