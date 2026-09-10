# Baseline — task B14H `artifact-retrieval-hard`

Date: 2026-09-10. Bare condition, 3 attempts per cell (Harbor 0.22.0, sealed network with the model API allowlisted, `-n 2`). Raw rows: `b14h-artifact-retrieval-hard-baseline.jsonl` (frontier) and `b14h-artifact-retrieval-hard-baseline-cheap.jsonl`. The store holds fourteen seeded runs produced by real executions at image build: finance's late-August backfill in which three days were re-processed with corrected exports (one re-processing failed), the cron week, and a typo run. Versus B14 (6/6): the criterion is a business rule with supersession, the largest completed backfill total belongs to a superseded run, and the report must cite the artifact's ZenML name and version number.

| harness | model | pass rate | docs read | hit the typed-parameter error | `get_artifact_version(name, version)` | `load_artifact` in the step | `region_report` runs | median tokens | mean cost |
|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | 3/3 | 3/3 | 2/3 | 1/3 | 0/3 | 1 | 599k | $0.57 |
| codex | gpt-5.6-terra | 3/3 | 3/3 | 2/3 | 0/3 | 2/3 | 1–2 | 750k | $0.33 |
| claude-code | claude-haiku-4-5 | 1/3 | 3/3 | 2/3 | 1/3 | 0/3 | 2–3 | 1.8M | $0.39 |
| codex | gpt-5.4-mini | 3/3 | 3/3 | 2/3 | 2/3 | 2/3 | 1–2 | 2.1M | $0.38 |

## What they did (all twelve read by marker; four read line by line)

Every trial listed the `backfill` runs through the client, grouped them by the `load` step's `date` parameter, kept the latest completed run per day and compared totals: the supersession rule was applied correctly in 12/12, including by the two Haiku trials that failed. Nobody picked a distractor (the failed 08-26 first pass at 17.2k, the superseded 08-27 first pass at 16.7k, the failed 08-25 re-processing at 17.0k, or scheduled 09-08 at 22.4k). Wording the criterion as a business rule did not cost the frontier models anything; the day the rule identifies (08-26, second pass, `daily_report::summarise::output` v5) was found in every trial and cited correctly in every report.

What the hard variant did change is *how the artifact reaches the step*, and that is where the cheap Claude Code trials fell:

- **The typed-pipeline-parameter error fired in 8/12 trials** (2/3 in every cell), up from 2/6 on B14. Agents write `def region_report(summary: dict[str, Any])`, pass the artifact version, and get "Only JSON serializable inputs are allowed as pipeline inputs". The frontier models and gpt-5.4-mini recovered by removing the annotation or by resolving the version inside the pipeline function (Codex's "graph construction" route) or with `load_artifact` in the step. **Both failed Haiku trials recovered the wrong way**: one loaded the version inside the step with `Client().get_artifact_version(...).load()`, the other passed `version.load()` (a plain dict) as the pipeline parameter. Both runs completed and both reports were right (west, 5537.81, v5), but the step had no recorded input (`input_types=0` in the grader's metrics), which is exactly the "copy of the numbers, not the artifact" case the instruction rules out. `Client().get_artifact_version()` inside a step does not register an input; `load_artifact()` does.
- **Name + version lookup is recorded no differently from lookup by id.** 4/12 trials fetched the version with `get_artifact_version("daily_report::summarise::output", "5")`, 4/12 called `load_artifact` in the step, the rest passed the version object taken from the run's `summarise` output. The step-run input holds the version id, name and number either way, so the requirement to cite name and version in the report is what makes the lookup visible to the grader (see decisions).
- One Claude Code frontier trial and one Haiku trial deleted their *own* failed `region_report` runs before re-running (the instruction forbids deleting `daily_report` runs only). Harmless here; a grader that counted `region_report` failures would have missed them.

## Findings

1. **Still saturated at the frontier (6/6)**; the business-rule wording and the supersession twist did not separate opus-5 from gpt-5.6-terra. The spread appears one tier down: Haiku 1/3 against gpt-5.4-mini 3/3, and the Haiku failures are lineage failures, not selection failures. `difficulty_estimate` set to `medium` on that basis (B14 is `easy`).
2. **The typed-parameter trap fires more often once the step also needs the artifact's name and version.** Agents now have three values to route into the step and reach for annotations; the docs sentence proposed in `docs/findings.md` for B14 ("annotated pipeline arguments are validated as JSON parameters") would remove most of the extra tokens, and a second sentence is due: "loading through `Client()` inside a step records no input; use `load_artifact` or pass the version into the pipeline".
3. **Every model applied the supersession rule from the `load` step's `date` parameter**, not from run names. The store's step configuration is the reliable key here (run names carry a `{time}` suffix for manual runs); this is the mechanism B10's decisions entry identified for graders, and the agents found it unprompted.
