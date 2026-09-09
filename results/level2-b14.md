# Baseline — task B14 `artifact-retrieval`

Date: 2026-09-09. Frontier tier only, bare condition, 3 attempts per cell (Harbor 0.22.0, sealed network with the model API allowlisted). Raw rows: `b14-artifact-retrieval-baseline.jsonl`. The store holds eleven seeded runs produced by real executions at image build: a hand-run backfill of late August (tagged `backfill`, one failed in `write_report` with the largest summary of all, one failed in `load`), the cron week (one completed scheduled day beats every backfill day), and a typo run.

| harness | model | condition | pass rate | docs read | hit the typed-parameter error | `region_report` runs | median tokens | mean cost |
|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | 3/3 | 1/3 | 1–2 | 284k | $0.33 |
| codex | gpt-5.6-terra | bare | 3/3 | 3/3 | 1/3 | 1 | 385k | $0.20 |

## What they did

All six went to the Python client, listed `daily_report` runs (Codex also via `zenml pipeline runs list --tags backfill`), loaded every candidate's `summarise` output with `.load()` and compared totals in code. Codex filtered by tag and status in the query (`list_pipeline_runs(tags=["backfill"], status="completed")` in 2/3); Claude Code listed everything with `hydrate=True` and filtered in Python. Nobody picked the failed 08-26 backfill (largest total) or the scheduled 09-08 run (largest completed total), and nobody recomputed from the CSV: the instruction's wording ("completed", "tagged backfill", "the artifact version ZenML recorded") was followed literally. One Claude Code trial cross-checked against `reports/2026-08-*.json` on disk, which is a legitimate shortcut for *finding* the run since the failed day has no report file.

Every trial fetched the version with `Client().get_artifact_version(<id>)` and passed it straight into the pipeline call; 5/6 first searched the docs snapshot for `ExternalArtifact` and then chose the direct route. Two trials annotated the pipeline parameter (`summary: dict`) and got ZenML's "Only JSON serializable inputs are allowed as pipeline inputs" error; both dropped the annotation on the next attempt. The grader's `input_types` metric is 1 for all six (a single input type, `external`); nobody used `load_artifact` inside the step.

## Findings

1. **Saturated at the frontier tier (6/6)**, and the distractors did not bite because the criteria were stated exactly. A harder variant: state the criterion in business terms only ("the busiest backfilled day finance asked about"), add a second `backfill`-tagged run that *re-processed* the same date later with different data (so "largest total" and "the run finance meant" diverge), or require the pipeline to load the artifact by name and version rather than by id.
2. **The typed-pipeline-parameter error is a real trap** (2/6 hit it, both recovered in one step). The docs snapshot shows untyped pipeline parameters in the artifact-passing example but never says why; one sentence ("pipeline arguments with a type annotation are validated as JSON parameters; leave the parameter unannotated or `Any` to pass an artifact version") would remove it. Recorded in `docs/findings.md`.
3. **Both harnesses read the docs 6/6 here**, unlike B10 (3/12): "how do I pass an old artifact into a pipeline" is recognised as a ZenML-specific question, "why did my run fail" is not. That is a useful split for deciding what a skill should cover: the debugging path, not the authoring path.
