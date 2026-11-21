# Kitaru Level 2: first baseline on ten tasks

Run on 2026-11-21 on Modal (workspace `zenml-io`, environment `dev`), Harbor 0.26.0, Kitaru 0.27.7, bare condition (CLI, SDK, offline docs; no skills, no MCP), 5 attempts per cell, 30-minute agent limit. Rows: `results/kitaru-<task>-baseline.jsonl`. Raw jobs: `jobs/kbaseline-*` and `jobs/kbaseline2-*` (not committed). C2 is in `results/kitaru-level1.md`.

Passes out of 5:

| task | what the agent must do | Claude Code + `claude-sonnet-5-5` | Codex + `gpt-5.6-terra` | Codex + `gpt-5.4-mini` |
|---|---|---|---|---|
| C1 rule from built-ins | apply a "no more than three lookups" rule to one week with a built-in evaluator | 5 | 5 | 0 |
| C3 evaluator is wrong | correct an evaluator that fails conversations it should pass | 5 | 5 | 1 |
| C4 backfill one release | run a corrected evaluator on one release only | 5 | 5 | 3 |
| C5 agree with reviewers | write an evaluator that reaches 40 human verdicts and holds on unseen conversations | 3 | 0 | 0 |
| C6 check before merge | a script that evaluates a cohort and exits 0, 1 or 2 | 1 | 1 | 0 |
| D6 refunded too much | cohort of every conversation that paid back more than the order cost | 3 | 5 | 0 |
| D7 slower, no release | cohort of conversations served by a silently changed model, cause, first day | 5 | 4 | 0 |
| D8 six to read | investigation of three to six real mistakes from one week, two kinds, verdicts | 5 | 5 | 0 |
| D9 retries or traffic | one cohort and one cause for each of two cost spikes | 4 | 4 | 0 |
| I3 write an importer | importer for a home-made log, graded on a hidden log | 5 | 5 | 0 |
| **total of 50** | | **41** | **39** | **4** |

Spend about US$37 for 180 trials (the 150 above plus the first runs of C6 and D6, see below). Median cost per trial: `gpt-5.4-mini` US$0.06 to 0.12, `claude-sonnet-5-5` US$0.11 to 0.21, `gpt-5.6-terra` US$0.26 to 0.52. No infrastructure exception in any trial.

## Two tasks changed after their first run

- **C6.** First run 1 of 15. Fourteen scripts evaluated the whole cohort in one request; Kitaru refuses more than 100 session-evaluator pairs per request, the hidden cohorts hold 130 conversations, and the only cohort in the workspace holds 40. The instruction gave no size, so this was a requirement the agent could not see. One sentence was added ("expect a few hundred conversations in one cohort") and the task re-run: 2 of 15, the same failure in all 13. The table shows the re-run; the first run's rows are in `results/kitaru-c6-check-before-merge-first-instruction.jsonl`.
- **D6.** First run 1 of 15 against the key as it then was (a second trial was graded after the correction), and the key was wrong. It held the 38 conversations where one refund call exceeded the order total. Eight of the nine strong-model trials that produced a cohort returned 49: those 38 plus 11 orders refunded twice in full. Twice the total went back, so they belong. The key now counts the total paid back, the instruction says "in total", the old reading is a shortcut that scores 0, the four checks were re-run on Modal, and the baseline was re-run. The table shows the re-run.

## What the failures were

Read from each failed trial's `verifier/metrics.json`; trajectories read where noted.

- **C1, `gpt-5.4-mini` 0/5: the wrong built-in.** Four trials ran `kitaru/tool-call-patterns` or `kitaru/trajectory-signals`, which describe repetition and give no pass or fail; one ran the team's `refund-issued-once`. None passed the rule to `kitaru/tool-policy` as a parameter. Final messages all say done.
- **C3, `gpt-5.4-mini` 1/5: edited the file, never registered it.** Three trials changed `evaluators/polite_closing.py` and stopped; Kitaru still held version 1. One registered a version that fails 96 of 120 hidden conversations.
- **C4, `gpt-5.4-mini` 3/5: evaluated the wrong set.** Two trials evaluated the 40-conversation reviewed cohort (or the 10 of it from release 1.4.1) and reported the release done.
- **C5, all 12 failures.** Every `gpt-5.6-terra` trial and one Sonnet trial produced the same evaluator: precision 0.85 with seven false alarms, three of them refunds on day 30 (the README says day 30 is inside the window) and four other correct refunds. They agree with all 40 reviewed conversations and lose it on the unseen ones. `gpt-5.4-mini` found at most one of the two rules.
- **C6, 13 of 15.** One `kitaru session evaluate --cohort ... --wait` for the whole cohort; exit 2 on all four hidden cohorts. The limit is stated in `guides/deterministic-evaluations.md`. No failing trial built a cohort larger than 100 to try its script on.
- **D6, Sonnet 3/5: two trials hit the 30-minute limit** with no cohort created; the two slow passes took 22 minutes. `gpt-5.6-terra` took 2.5 minutes. `gpt-5.4-mini` built cohorts of 1 to 27 conversations with no affected one in them.
- **D7.** `gpt-5.6-terra`'s one failure and two `gpt-5.4-mini` trials named the right cause and put the start one or two days late (10 or 11 July, when most conversations were affected, against 9 July when the first was). Sonnet's five passes took about 13 minutes each against 1.3 for `gpt-5.6-terra`.
- **D8, `gpt-5.4-mini` 0/5:** conversations from outside the week (3 trials), conversations with no mistake marked problematic (2), verdicts never set (1); one trial did two of these.
- **D9.** Both large models lost one trial the same way: the whole promotion day (166 or 172 conversations) in the second cohort, not the 120 the promotion brought.
- **I3, `gpt-5.4-mini` 0/5:** three importers crashed on the hidden log (the import job failed, nothing stored); two trials never registered an importer.

## Reading

- The set separates the small model from the two large ones on nine tasks of ten, and separates the two large ones on C5 and D6 only. With 5 attempts per cell, a difference of one is not a difference.
- **Saturated for both large models: C1, C3, C4, D8, I3** (5 of 5 each). By the proposal's rule each needs a harder variant or moves to a regression list. C2 was already there.
- **Hard for everyone: C5 and C6.** C5's trap is a rule stated in the README. C6's is a documented limit that only shows at a size the workspace does not contain.
- Not done: the `+ skills` and `+ MCP` conditions; a read of every passing trajectory; a second model family for Claude Code.
