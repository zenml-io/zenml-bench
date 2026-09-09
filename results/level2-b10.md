# Baseline — task B10 `why-did-it-fail`

Date: 2026-09-09. Same setup as `level1.md`: Harbor 0.22.0, sealed network with the model API allowlisted, 3 attempts per cell. Raw rows: `b10-why-did-it-fail-baseline.jsonl` (frontier) and `b10-why-did-it-fail-baseline-cheap.jsonl`. The store holds six seeded runs produced by real executions at image build; the instruction names neither the date nor the cause.

| harness | model | condition | pass rate | skill read | found `exception_info` | read log files on disk | tried a non-existent API | median tokens | mean cost |
|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | – | 0/3 | 2/3 | 3/3 (`step.logs`) | 476k | $0.58 |
| claude-code | claude-opus-5 | + skill | 3/3 | 0/3 | 0/3 | 2/3 | 3/3 (`step.logs`) | 445k | $0.49 |
| codex | gpt-5.6-terra | bare | 3/3 | – | 1/3 | 3/3 | 2/3 (`zenml pipeline runs describe`) | 271k | $0.19 |
| codex | gpt-5.6-terra | + skill | 3/3 | 3/3 | 3/3 | 2/3 | 3/3 (`zenml pipeline runs describe`) | 383k | $0.23 |

Cheap models (bare, 3 attempts each): see the section at the end.

## How they found the cause (all 12 frontier trials read by marker; three read line by line)

Every trial went to the store first and none re-ran blindly: `zenml pipeline runs list` (12/12), then the Python client (`Client().list_pipeline_runs`, 11/12; the twelfth used only the CLI plus the log files). Codex filtered on the CLI (`--tags scheduled --status failed`) in 5/6 trials; Claude Code listed everything and filtered by eye. Nobody fell for the most-recent-failure distractor (the manual typo run): every trial keyed on the `scheduled` tag or the `scheduled-<date>` name, as the instruction said. Nobody re-fixed the `reports/` distractor either. The metrics recorded per trial (`agent_runs`, `agent_failed_runs`) show one wasted run at most, except one Claude Code + skill trial whose first edit was wrong and took two failed runs to correct.

Where the harnesses differed is in *how they read the failure*:

- **Claude Code (6/6) asked the step run for `.logs`**, an attribute that does not exist on `StepRunResponse` in 0.96.4, caught the exception, then went looking for log files: `find / -name "*.log"` and grepping under `~/.config/zenml/local_stores/<store>/logs/` (4/6). It never found `step.exception_info`, which holds the traceback, exception class and message in one attribute. Two trials skipped the traceback entirely: once the step name was `parse`, they opened `data/2026-09-09.csv`, saw the quoted `"1,234.50"`, and fixed it.
- **Codex (5/6) called `zenml pipeline runs describe`**, a command that does not exist, read `--help`, then switched to the client. 4/6 Codex trials found `exception_info` (typically after `inspect`/`dir()` on the step object or after reading the docs snapshot), the rest read the same on-disk log files.

All 12 fixes strip the separator in `parse` (`str.replace(",", "")` on the string form, or `pd.to_numeric` after replacing) or, in one case, `read_csv(thousands=",")`. All 12 also checked the other days still parse, which is exactly what the second hidden fixture tests.

## Findings

1. **Saturated at the frontier tier**, like B3/B5/B9. The distractors cost nobody anything once the instruction said how scheduled runs are identified. A harder variant should withhold that ("a run failed this morning") so the agent has to establish which run is the cron's from the store alone, and could add a second real fault on another day so "fix the one failing step" is not enough.
2. **Both harnesses guessed an API that is not there.** `StepRunResponse.logs` (Claude Code, 6/6) and `zenml pipeline runs describe` (Codex, 5/6). Both guesses are reasonable, and both would be good additions: a `describe` subcommand that prints step statuses and each failed step's `exception_info`, and a `logs` convenience on the step response. Until then the docs snapshot should say plainly where a failed step's traceback lives (`run.steps[name].exception_info`) and that the CLI cannot show it. Filed as a docs/CLI item in `docs/findings.md`.
3. **The skill did not help Claude Code (0/3 read) and cost Codex tokens (+40%) without changing the outcome**; the pipeline-authoring skill has nothing on reading run state, so this is expected. A "debug a failed run" skill with the three lines above would be the direct fix.
4. **Grader metrics worked as instrumentation**: `agent_runs`, `agent_failed_runs` and `agent_runs_for_target` come straight from the store and needed no trajectory parsing.

## Cheap models (bare, 3 attempts each)

| harness | model | pass rate | found `exception_info` | re-ran the failing day before reading the cause | median tokens | mean cost |
|---|---|---|---|---|---|---|
| claude-code | claude-haiku-4-5 | 3/3 | 2/3 | 2/3 | 709k | $0.14 |
| codex | gpt-5.4-mini | 3/3 | 3/3 | 0/3 | 349k | $0.10 |

Saturated here too, at 18/18 overall. Two things differ from the frontier tier. First, the cheap models found `step.exception_info` *more* often (5/6 vs 4/12): they asked the client for the run object and printed its fields instead of guessing an attribute name. Second, two of the three haiku trials used the store only to find the run's name and date, then reproduced the failure by re-running `python run.py --date 2026-09-09` themselves (the grader's `agent_failed_runs` metric shows the extra failed run), and one of them then hit `EntityExistsError` by re-running with `--trigger scheduled` before running it plainly. Cheap Claude Code also guessed two more non-existent commands (`zenml run list`, `zenml pipeline runs get`). Blind re-running is cheap on a 46-row CSV; on a real pipeline it is the behaviour a benchmark should penalise, which argues for a variant whose failing step is expensive or whose input is no longer on disk.
