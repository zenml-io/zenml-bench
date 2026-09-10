# Baseline — task B10H `why-did-it-fail-hard`

Date: 2026-09-10. Bare condition, 3 attempts per cell (Harbor 0.22.0, sealed network with the model API allowlisted, `-n 2`). Raw rows: `b10h-why-did-it-fail-hard-baseline.jsonl` (frontier) and `b10h-why-did-it-fail-hard-baseline-cheap.jsonl`. The store holds ten seeded runs produced by real executions at image build. Versus B10 (18/18): the instruction never says how scheduled runs are recorded, the two failed days' exports are quarantined off the box, and a second scheduled failure six days earlier (region spellings, `summarise`) is also a code fault the instruction requires fixing ("reliable again").

| harness | model | pass rate | read `bin/nightly.sh` | `step.exception_info` via client | read log files under `local_stores/` | queried the SQLite store directly | re-ran the quarantined day | tried a non-existent API | median tokens | mean cost |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | 3/3 | 3/3 | 0/3 | 3/3 | 0/3 | 0/3 | 3/3 (`step.logs`) | 1.24M | $1.37 |
| codex | gpt-5.6-terra | 3/3 | 3/3 | 0/3 | 3/3 | 2/3 | 0/3 | 1/3 (`runs describe`) | 392k | $0.28 |
| claude-code | claude-haiku-4-5 | 1/3 | 2/3 | 0/3 | 3/3 | 3/3 | 1/3 | 2/3 | 2.65M | $0.51 |
| codex | gpt-5.4-mini | 3/3 | 3/3 | 2/3 | 3/3 | 3/3 | 0/3 | 2/3 | 958k | $0.21 |

Columns after "pass rate" are string markers over tool-call arguments plus three trajectories per task read line by line; "re-ran the quarantined day" is the grader's own `agent_runs_for_quarantined` metric.

## What they did

**Finding the run.** Every trial that passed read `README.md` → `bin/nightly.sh` → `run.py` and knew within the first three tool calls that cron runs carry the `scheduled` tag and the `scheduled-<date>` name. Removing that sentence from the instruction moved it two files away; it did not hide it. Codex then filtered on the CLI (`zenml pipeline runs list --status failed`, `--tags scheduled`), Claude Code listed everything through the client. The manual typo run (most recent failure) and the manual ISO-timestamp run (a code-looking failure that is not scheduled) fooled nobody who read the tags.

**Reading the cause with no file to re-run.** This is where the variant changed behaviour. In B10, 4/12 frontier trials found `step.exception_info`; here 0/6 did, and the routes got more creative:

- Claude Code (opus) asked for `step.logs` again (3/3), fell through to `find / -name "*.log"` and read the step log files under `~/.config/zenml/local_stores/<store>/logs/`, where the full traceback sits as JSON lines. 3/3.
- Codex (terra) read the same log files, and 2/3 opened the SQLite store itself (`sqlite3 ~/.config/zenml/local_stores/default_zen_store/zenml.db`, then `select ... exception_info from step_run`). One trial wrote a Python script over the raw tables.
- The cheap models did the same, harder: Haiku queried SQLite in 3/3 trials, gpt-5.4-mini in 3/3 (and 2/3 also called `.exception_info` on the step object after listing its fields). One gpt-5.4-mini trial asked the CLI for `--columns=...,exception_info` on the *run*, which is empty for a step failure, then moved on.
- Nobody read the quarantined data back from the `load` step's output artifact, the route the decisions entry describes; the traceback message (which quotes the offending values) was enough for everyone who found it.
- One opus trial (c9oYrqc) reconstructed the restore scenario with a synthetic 2026-09-09 export in `/tmp`, ran the pipeline there, then deleted that run from the store. It also changed the scheduled run-name format to `scheduled-<date>-{time}` "so a restore re-run cannot clash". The grader has no check on the run-name format, so this passed; it is a real collateral change (see findings).

**Fixing.** All 9 passing trials normalised region spellings (`str.strip().str.lower()`) and stripped the separator (or `thousands=","`), then ran the five on-disk days as the instruction asked (grader `agent_completed_days=5`, `agent_failed_runs=0` in 8/9). 4/9 also hardened the two non-code failures (`os.makedirs("reports")`, lenient timestamps), which the grader accepts.

**The two Haiku failures are the behaviours the variant was built to catch.**

- AnjvJQV (48 agent runs, 3 of them on the quarantined dates): it re-ran `--date 2026-09-09`, got `FileNotFoundError` in `load` (the file is gone and `load` is uncached), and its final message says "while I couldn't see the exact error, the code had several vulnerabilities". It coerced amounts with `errors="coerce"`, timestamps likewise, and filtered rows to known regions. Every run completes; the restored 2026-09-09 export comes back with 43 rows instead of 46 and `hidden_sep` loses 5 rows. Failed on the row count, exactly like `drop_bad_rows.sh`.
- SijkmUZ: found the 2026-09-03 traceback (region spellings) and attributed it to this morning's run, deleted the row-accounting check in `summarise` and never touched `parse`. Its own five proof runs passed because no day on disk has a separator amount. Failed on the restored export and on `hidden_sep` with the original error, `could not convert string to float: '1,234.50'`, the same way `fix_only_second_cause.sh` does.

## Findings

1. **Frontier still 6/6, so the hint removal did not open a gap at the top; it roughly doubled Claude Code's cost** (1.24M tokens median, $1.37, against 476k and $0.58 on B10) while Codex stayed flat (392k against 271k). The gap opened one tier down: Haiku 1/3 against gpt-5.4-mini 3/3. `difficulty_estimate` set to `medium` (B10 is `easy`).
2. **Which removal did the work.** Naming and tagging: none, every model found them in the project files. Quarantining the export: this is what separated the tiers. With the file present (B10) Haiku re-ran the day to see the error in 2/3 trials and passed 3/3; with the file gone it re-ran, saw a *different* error, and 2/3 trials guessed a fix. The second fault: it caught one Haiku trial (SijkmUZ) that fixed only what it had read, and it is what makes `fix_only_first_cause.sh` a shortcut, but no frontier trial fixed only one cause.
3. **Nobody at any tier reaches `step.exception_info` through the client when the file is gone (2/12, both gpt-5.4-mini).** The observed substitutes, in order of frequency: the step log files on disk (12/12), the SQLite database (8/12), guessing `step.logs` or `zenml pipeline runs describe` (8/12). Reading the store's private database is a route that only exists on the local SQLite stack; against a ZenML server it would not. The docs and CLI items from B10 stand and are now measurable one tier down: a `zenml pipeline runs describe` that prints each failed step's `exception_info`, and a docs sentence pointing at `run.steps[name].exception_info` and `step.resources.log_collection[*].uri`.
4. **Collateral to add for a v0.2 of this task**: the scheduled run-name format (`scheduled-<date>`, no time suffix) and the `scheduled` tag must survive, since one opus trial changed them and cron's identification would silently change with it. Not added now because the instruction does not state it; it should, and then the grader can check it by running `--trigger scheduled` on a hidden day.
