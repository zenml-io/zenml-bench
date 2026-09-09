# Findings from baselines

What agents actually did, what broke, and what it points at (docs, skill, MCP, or our own task). Newest at the bottom. Feed each item into a fix and re-run the task that exposed it.

## 2026-09-09 — first Codex trial on B3 (gpt-5.6-terra, bare, 1 attempt)

- **Outcome:** correct fix, scored 0 because of a grader bug. Codex computed a SHA-256 of the data file in the pipeline function body and passed it into `load_data` as a parameter: a valid fourth solution (not one of our three). It read `/opt/zenml-docs/llms-full.txt` with `rg` for "cache" and "file", ran the pipeline five times, edited the CSV to test, restored it, and explained the mechanism correctly in its final message.
- **Grader bug:** the test asserted `train` executed on the grader's first run (dataset a). The agent had already run the fixed pipeline on dataset a, the ZenML store is shared between agent and grader, so the first run was a legitimate cache hit. Fixed by dropping that assertion; `solution/alternatives/solve_then_run_twice.sh` now guards it. **General rule for graders:** anything the agent could have run before grading may be cached; only assert "executed" on inputs the agent has never seen.
- **Instrumentation:** `docs_read=True`, `pipeline_runs=5`, `steps=18`, `tool_calls=12` from `analyse_trajectories.py`. Codex's tool calls are JavaScript `exec` blocks wrapping `tools.exec_command` and `tools.apply_patch`, so the string markers worked but the `pipeline_runs` count includes the agent's own test runs.

## 2026-09-09 — Level 1 baseline (2 harnesses × 2 conditions × 3 attempts)

See `results/level1.md` for the table. Headlines: 12/12 pass, so B3 is saturated for opus-5 and gpt-5.6-terra; Claude Code read the ZenML skill in 0/3 trials while Codex read it in 3/3; all trials read the offline docs; the skill nudged Codex toward `CachePolicy` (the built-in feature) instead of the hand-rolled hash step. Next actions: (a) check Claude Code's skill listing/description matching, (b) build harder tasks (B7 Kubernetes settings, B9 modernise old API, B5 materializer) where docs-reading alone should not suffice.

Follow-up on the Claude Code skill result (Alex, 2026-09-09): Claude Code discovers project skills in `<repo>/.claude/skills/` and Codex in `<repo>/.agents/skills/`. Harbor copied the skills into the user-level `$CLAUDE_CONFIG_DIR/skills` it creates for the trial, so the 0/3 may mean "never delivered" rather than "ignored". Test: put the skills at `/app/nightly/.claude/skills/` (via `[environment].skills_dir` or the Dockerfile) and re-run one Claude Code trial; if it reads the skill, the baseline runner must place skills per harness.

**Resolved (2026-09-09, skill probe):** a probe task asked each agent to list the skills it could see. Both Claude Code and Codex listed `pipeline-authoring` and `quick-wins` (Harbor's copy into `$CLAUDE_CONFIG_DIR/skills` / `~/.agents/skills` works). So Claude Code's 0/3 on B3 was a *choice not to invoke*, not a delivery failure. The description Claude Code saw, "Author ZenML pipelines: @step/@pipeline decorators, artifact flow, YAML config, Docker/Resource settings, materializers, hooks, and visualizations", does not mention caching, so a caching bug did not match. Actionable for `zenml-io/skills`: add caching / cache policies (and other common failure areas) to the `pipeline-authoring` description, then re-run B3 with Claude Code. Codex reads skills more eagerly (3/3) regardless.

## 2026-09-09 — first B7 baseline (kubernetes-settings): the grader was wrong, the agents were right

- All 9 bare/codex-skill trials scored 0 on one assertion: the grader wanted `pod_settings.service_account_name`, a field that does not exist on `KubernetesPodSettings` (see decisions). The agents used `step_pod_service_account_name`, which is what the orchestrator reads.
- **How they knew:** neither `llms-full.txt` nor the `pipeline-authoring` skill mentions step-pod service accounts. Every trajectory shows the agent opening `zenml/integrations/kubernetes/...` under site-packages and reading `service_account_name=settings.step_pod_service_account_name or settings.service_account_name`. Both harnesses treat the installed package as documentation of last resort. Docs gap worth filling: the Kubernetes orchestrator page should list `step_pod_service_account_name` / `service_account_name` and say `pod_settings` does not carry one.
- The 3 Claude Code + skill trials passed the old grader because they set both fields.
- Baseline is being re-run with the corrected grader; see `results/level2-b7.md` when it lands.

## 2026-09-09 — first B5 baseline (custom-materializer): grader bug, third of the shared-store family

9/9 trials wrote a custom materializer (8) or made the type picklable (1) and produced correct scores, then scored 0 because the grader asserted the named artifact was *produced by* the graded run. The agents had run the fixed pipeline; the grader's run served `train` from cache, so the artifact's producer was their run. Fixed (assert the graded run's `train` output is the artifact) and `solve_then_run_twice.sh` added, which now exists for every task. One Claude Code trial also left a helper pipeline `check` registered; the instructions now state "leave no other pipelines registered". Matrix re-run pending.

## 2026-09-09 — fixes shipped upstream from the first findings

- zenml-io/zenml#5266 "Document `step_pod_service_account_name` for Kubernetes step pods" (docs; states the fallback order and that `pod_settings` carries no service account). https://github.com/zenml-io/zenml/pull/5266
- zenml-io/skills#10 "Add caching and settings triggers to `pipeline-authoring` skill description" (description names caching, stale cache results, resource/orchestrator settings, materializers for custom types; plugin.json bumped to 1.0.3). https://github.com/zenml-io/skills/pull/10

Both requested review from bcdurak. To measure: once merged, rebuild the base image (docs snapshot), bump `SKILLS_SHA` in `run_baselines.py`, re-run B3 and B7 with Claude Code + skill and compare skill-read rate and tokens against `results/level1.md` / `level2-b7.md`.
