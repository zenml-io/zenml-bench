# Writing a task

Everything here was learned by building B3, B9 and B7 on 2026-09-09. Follow it and the four checks will pass the first time more often.

## The shape

```
tasks/<id>/
├── task.toml                 # Harbor schema 1.4; [metadata] carries provenance (see below)
├── instruction.md            # what the agent is told; states the contract the grader relies on
├── environment/
│   ├── Dockerfile            # FROM zenml-bench/base:<pin>; COPY <project>; zenml init; optional setup_store.sh
│   ├── <project>/            # synced copy of shared/projects/<project> (scripts/sync_project.sh); never edit here
│   └── setup_store.sh        # optional: register stack components; also run by grade_local.sh
├── solution/
│   ├── solve.sh              # reference; patches the project in place; honours APP_DIR
│   └── alternatives/*.sh     # other valid solutions; at least one, and one that behaves like a real agent
└── tests/
    ├── test.sh               # runs pytest, writes /logs/verifier/reward.txt
    ├── test_<id>.py          # the grader
    ├── fixtures/             # data the agent never saw + expected.json
    └── shortcuts/*.sh        # solutions that must score 0
```

`[metadata]` in `task.toml`: `family`, `tier`, `difficulty_estimate` (update after baselines), `zenml_version`, `source` (where the task came from), `conditions_supported`.

## Workflow

1. **Spike first, in the shared project, without Harbor.** Write the project, reproduce the fault, apply the fix you have in mind, and *read the store with the client* (`run.steps[name].status`, `.outputs`, `.config.parameters`, `.config.settings`). Assertions come from observed state. Every task so far had one assumption that was wrong until this step (B3: how cache keys treat artifact IDs; B9: tuple returns; B7: settings dropped at compile).
2. Write the grader and the reference, then `scripts/grade_local.sh <task> solution/solve.sh`. Iterate here; it takes ~25 s.
3. Write shortcuts and alternatives; run each through `grade_local.sh`. Use `VERBOSE=1` to see which assertion each shortcut trips. A shortcut should fail on the check *designed* for it, not on an unrelated crash.
4. `scripts/sync_project.sh <project> <task>`, then `uv run scripts/verify_task.py <task>` (Harbor, ~1–2 min per run).
5. Baseline with `scripts/run_baselines.py`; read three trajectories by hand; put what you saw in `docs/findings.md`; update `difficulty_estimate`.

## Grader rules (each one cost us a bug)

- **Grade recorded state, not source text.** A run exists, a step was `CACHED`, an output has a name, a parameter value is in the step config, a compiled deployment has a setting. Never grep `run.py` for the right line.
- **The store is shared between the agent and the grader.** Anything the agent could have run before grading may be sitting in the cache. Only assert "this step executed" on inputs the agent has never seen, or expire earlier step runs first (`Client().update_step_run(id, cache_expires_at=now)`), as B9 does.
- **A cached step's output belongs to an earlier run.** If the grader's run hits the cache, a named artifact's `producer_pipeline_run_id` points at the agent's earlier run. Don't assert on the producer; assert that the graded run's step output *is* the named artifact version (B5). And "latest version by name" may be a *debug* run's version while the graded run gets an older cached one; assert the graded run's output is *a version of* the named artifact, never that it *is* the latest. Every task needs `solve_then_run_twice.sh` and, where artifacts are named, `solve_debug_then_revert.sh` alternatives to catch this class.
- **The oracle is the least realistic agent.** It applies the fix and stops. Add an alternative that also runs the pipeline a few times before grading (`solve_then_run_twice.sh` in B3), or a real agent will find the gap.
- **Run the agent's entrypoint yourself** with the grader's own fixtures, and identify the run *you* created (diff the set of run ids before/after). Don't trust "most recent run".
- **Accept every valid method.** If the instruction doesn't name the method, the grader must not require it: assert on the expensive step's cache status, not the cheap one's; search parameter values whether flat or nested in a model; accept GPU/memory in either ZenML form.
- **Unseen data defeats hardcoding.** At least one fixture the agent could not have seen, with an expected value computed by the reference.
- **Collateral checks.** Pipeline name unchanged, no extra pipelines registered, active stack unchanged, other steps' settings unchanged.
- **Kubernetes-style settings never reach the run record on a local stack.** Register a clusterless Kubernetes stack in the image and grade by dry-run compile (B7's grader shows how); read compiled settings under `orchestrator:<component-name>`.
- **Research tasks: a link is not evidence.** `link_artifact_version_to_model_version` attaches any artifact to any model version, and a cached repeat run re-links an old artifact. Grade the producer chain: production version → linked run that is `COMPLETED` and of the right pipeline → its `train` step → an output whose `producer_step_run_id` is that step. Score only the newest artifact that survives the chain, with the grader's own metric on hidden data (R1's `tests/verify.py`).
- **If you want to check it, make the pipeline record it.** A rule the grader cannot read from the store is a rule the instruction merely hopes for (R1's "train on the seed's slice" was that for a day). Give the step an extra output that records the fact (a row count, a digest of the rows, a parameter echo) and check that output through the same producer chain as the artifact it sits next to; recompute the expected value from the grader's own copy of the data, never from the agent's files. Ship a shortcut that records the violation honestly (`train_on_full_set.sh`) and an alternative that is legitimately different but within the rule (`feature_engineering_in_train.sh`), so the check is neither hollow nor over-strict. The residual gap is that agent-controlled code writes the record; that turns "ignore the rule" into "falsify the record", which is the most a store-based grader can do.
- **Budgets bind on what the agent actually spends.** Pilot trials showed a 12-run budget constrains bookkeeping, not search: fits take seconds and happen in off-loop scripts. Before adding a cost to a step, check whether the agent can pay it elsewhere; a cost inside the pipeline taxes only the honest agent. Wall clock binds because tool-call latency is the agent's real cost; state it in the instruction and enforce it with `[agent] timeout_sec` and `[environment] cpus` (see the 2026-09-10 comparison decision).
- **Scripts that build on the reference** must locate it via `REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"`. Under Harbor the script *is* `/solution/solve.sh`; a relative call recurses until the container dies.

## Difficulty

A task that frontier models solve 100% of the time is a regression test, not a benchmark, and gives a trainer no signal. Aim for tasks where reading one docs page is not enough: several details across pages (B7), behaviour that the docs describe only implicitly (cache keys and content hashes), or an old mental model to unlearn (B9). Record pass rates per harness after every baseline; that spread is the benchmark's calibration.
