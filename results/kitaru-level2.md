# Kitaru Level 2: baselines (ten tasks, then eight more)

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

## Second round: four import tasks and four harder variants

Run on 2026-11-21, same setup as above (Modal, Harbor 0.26.0, Kitaru 0.27.7, bare, 5 attempts per cell, 30-minute agent limit). Rows: `results/kitaru-<task>-baseline.jsonl`. Raw jobs: `jobs/kbaseline-*` (not committed).

Passes out of 5:

| task | what the agent must do | Claude Code + `claude-sonnet-5-5` | Codex + `gpt-5.6-terra` | Codex + `gpt-5.4-mini` |
|---|---|---|---|---|
| I1 import an export | register an agent with two releases and import a Langfuse export, each ticket under its release, under the right source identity | 5 | 5 | 0 |
| I2 one ticket, one session | a script that imports a Langfuse export so one session is one ticket; graded on a hidden export too | 5 | 5 | 1 |
| I4 nightly import twice | repair a nightly import script that began creating duplicates, and the store, keeping the sessions that were right | 5 | 5 | 0 |
| I5 invoice does not match | find why Kitaru's cost is a third below the bill, register a corrected importer version, get the month right | 5 | 5 | 0 |
| I3h messy log (harder I3) | importer for a log with batch calls that carry no cost, repeated lines, and a timestamp form the sample never shows | 5 | 5 | 1 |
| C1h two rules from built-ins (harder C1) | two rules, two built-in evaluators, one week; the obvious parameter for the second rule gives the rule breakers no verdict | 5 | 5 | 1 |
| C7 fix the check, then backfill (harder C3 and C4) | decide the check is wrong, register a corrected version, backfill one release, under a cap on results that counts every version | 5 | 5 | 0 |
| D8h triage check failures (harder D8) | link all 23 conversations two checks fail in one week and say for each whether the check is right | 5 | 5 | 0 |
| **total of 40** | | **40** | **40** | **3** |

Spend US$27.86 for 120 trials. Median cost per trial: `gpt-5.4-mini` US$0.08, `claude-sonnet-5-5` US$0.17, `gpt-5.6-terra` US$0.33. No infrastructure exception and no timeout in any trial. Median agent time: under 2 minutes on every import task for all three models; about 5 to 7 minutes on the three `storefront` variants for the large models, except Sonnet on C1h at 13 minutes.

### Reading

- **Every one of the eight tasks separates the small model from the two large ones, and none separates the two large ones.** The four harder variants did not make their tasks harder for the large models: 30 of 30 on the variants, as on the tasks they came from.
- **What the variants added, and how the large models met it.** I3h: a timestamp form that is in the format document and not in the sample; all ten large-model importers parse it. C1h: `require_requested_model_match` leaves `passed` empty for a dated variant of the requested model; seven of the ten large-model trials passed that parameter, and all ten also passed `allowed_models`, the one that states a failure. C7: a cap on results that counts every version; no large-model trial ran the old version at all (they read its source), and all ten ended with 464 to 760 results, every one from the corrected version, against a cap of 1,400. D8h: 23 conversations to link, each with a verdict; all ten investigations are exact.
- **By the proposal's rule (section 11, Level 2 done bar) these eight go on the regression list, with C1, C2, C3, C4, D8 and I3.** They are still worth running: each one caught the small model, in a way one of its shortcuts predicted.
- **What does separate the large models, across both rounds, is three things, and none of the eight has them:** a rule that has to be inferred from human verdicts and holds on unseen cases (C5: 3 and 0 of 5); a platform limit that only shows at a size the workspace does not contain (C6: 1 and 1); and "find every one" over the whole history, with a time limit (D6: 3 and 5; D7: 5 and 4; D9: 4 and 4). Longer chains of steps, and details stated in a document the agent is told to read, did not do it.

### What the failures were

All 37 failures are `gpt-5.4-mini`. Read from each trial's `verifier/metrics.json` and final message.

- **I1, 0/5: tickets not split by release.** In four trials about half the tickets sit under the wrong version (46 to 48 of 90 right); one of those also holds a second copy of every ticket under another identity (180 sessions). One trial imported nothing. One final message says the file was imported for 1.4.0, then again for 1.5.0 where all 90 were "skipped as duplicates, so there are no extra sessions": nothing went under 1.5.0. Another says "verified the final state has 90 sessions under each version".
- **I2, 1/5: the default grouping.** Two trials imported with the default grouping, so sessions follow the chat widget visit (78 sessions for 70 tickets, probes included); a third grouped wrongly another way (no ticket right). One wrote a correct script (hidden export 60 of 60) and left the day's export wrong (12 of 70 right).
- **I4, 0/5: the strays are never deleted.** No trial removed a session. Two repaired the script: one of them also re-imported the two nights (every ticket present under the right identity, 96 strays left), the other left the store as it was. Three left the script wrong; two of those made more strays (312 and 432 sessions against 168 tickets).
- **I5, 0/5: August untouched.** Three trials edited `importers/tw_trace.py` and registered nothing. Two registered a second version (one fully correct on the hidden log) and never re-imported: August still holds US$0.46 of US$0.67.
- **I3h, 1/5:** four importers crashed on the hidden log (the import job failed, nothing stored).
- **C1h, 1/5:** three trials stored no verdict from a built-in for either rule; one gave the lookup rule a verdict on 35 of 345 conversations.
- **C7, 0/5:** two "corrected" versions fail nearly every conversation of the release (6 curt among 464 failed); three trials evaluated 5 to 20 conversations and stopped.
- **D8h, 0/5:** two trials opened no investigation; three linked 0, 1 or 5 conversations, none of them one of the 23.

## Third round: one variant built on a property that had separated the large models

I4h, `i4h-strays-at-scale`, run on 2026-11-21, same setup. It is I4 plus one deliverable: `bin/remove_strays.sh`, which deletes every session under `support-assistant` whose external id does not start with `tidewater-support:`. The instruction says the script will run where the agent has "a few thousand sessions". The workspace holds 216. The grader imports 500 strays and then 1,200 good sessions (about 1,900 in all, the strays oldest) and runs the script.

| task | Claude Code + `claude-sonnet-5-5` | Codex + `gpt-5.6-terra` | Codex + `gpt-5.4-mini` |
|---|---|---|---|
| I4h strays at scale (harder I4) | 4 | 4 | 0 |

Spend US$3.48 for 15 trials. No infrastructure exception and no timeout. Median agent time 1.2 to 1.8 minutes.

- **Both large-model failures are the same script.** It lists sessions over REST, 1,000 per page, in a loop that reads the next page's cursor from `.page.next_cursor`. That is where the CLI's JSON output puts it. The REST response has `next_cursor` at the top level. The loop therefore ends after one page; the 1,000 newest sessions hold no stray, and the script reports "deleted 0 stray sessions" with exit 0. On the 216 sessions in the workspace one page is everything, so the script worked when its author tried it.
- **The eight passes** used the Python client's `sessions.iter()` or read the cursor from the right place.
- **`gpt-5.4-mini`, 0/5:** every removal script left every stray in place; one crashed on a client argument that does not exist. Three of the five had also repaired the store by hand.
- **Reading.** One failure in five for each large model is a small difference with five attempts, and I4 itself was 5 and 5. What it supports: the property that made C6 hard (a limit that only shows at a size the workspace does not hold) works a second time, where length and documented details did not. Unlike C6, most large-model trials got through, because one common route (the Python client) pages by itself.

## Fourth round: D1 to D5 on the `clinic` world

Run on 2026-11-21, same setup. All five tasks read one history: a veterinary chain's appointment assistant, 3,211 conversations from 1 June to 20 July 2026, and a repository with five dated commits.

Passes out of 5:

| task | what the agent must do | Claude Code + `claude-sonnet-5-5` | Codex + `gpt-5.6-terra` | Codex + `gpt-5.4-mini` |
|---|---|---|---|---|
| D1 wrong clinic | cohort of every booking confirmed at another clinic than the one asked for (269); the 13 complaints are other conversations | 4 | 5 | 0 |
| D2 was it the release? | cohort of the conversations that raised cost per conversation (207 new patients), and the cause; a release rolled out on the same days | 5 | 5 | 0 |
| D3 answers cut off | cohort of cut-off replies (288), the commit that caused it, the first day; no release went out | 5 | 5 | 0 |
| D4 what broke? | cohort of the failed calls that account for a tripled failure rate (67 refused group bookings), and the cause; nothing broke | 3 | 5 | 0 |
| D5 did the hotfix work? | cohort of wrong-clinic bookings under the release that was meant to stop them (98); an empty cohort is legal and wrong | 5 | 4 | 0 |
| **total of 25** | | **22** | **24** | **0** |

Spend US$15.28 for these 75 trials, and US$25.84 more for 131 trials in two earlier rounds that were discarded (see below). No infrastructure exception.

### Two tasks changed after their first runs

- **D2.** First run: Sonnet 2 of 5, `gpt-5.6-terra` 2 of 5. All six failures had exactly the right cohort and the cause `new_release`. The workspace's changelog said release 1.2.0 added the new-patient flow, so the answer was defensible. The line was removed; the re-run is 5 and 5.
- **D4.** First and second runs: `gpt-5.6-terra` 2 of 5 both times, with the right cohort and the cause given as a prompt change (five trials) or a traffic change (one). The label list contained a second true answer, and the history gave no way to tell whether the assistant had always attempted such bookings. D4 now has its own label list, and four group bookings are refused before the prompt commit. The re-run is 5 of 5.

Same lesson as D6 in the first round: when several strong trials agree on an answer the key calls wrong, check the key and the workspace before the agents.

### What the failures were

- **Sonnet, all three (D1 once, D4 twice): the 30-minute limit, with no cohort created.** Its passing D4 trials took 1, 19 and 20 minutes. `gpt-5.6-terra` took about 2 minutes on every clinic task. Not read from the trajectories why; the same was seen on D6 and D7.
- **`gpt-5.6-terra`, D5 once:** 127 members for 98. The extra 29 are group bookings that were refused: the test "the result's clinic differs from the one sent" is true when the result has no clinic at all.
- **In the discarded rounds, two more kinds, both from the tasks as they are now:** D1 answered with the 13 complaints (the planted trap) or with 60 of the 269; D5 answered with an empty cohort (the planted trap) twice in ten.
- **`gpt-5.4-mini`, 0 of 25.** D1: the complaints, every conversation in the history, or no cohort. D2: three trials named the right cause with a cohort of a quarter of the conversations or less. D3: all five named the right commit, and none built the cohort: one had no cohort, the others held 5, 85, 226 and 1,347 conversations for 288; three also gave a first day that was days late. D4: three built no cohort. D5: four empty cohorts.

### Reading

- **With five attempts per cell, the two large models are not separated on any clinic task**: the largest gap is D4 at 3 against 5, and all of Sonnet's losses are timeouts, not wrong answers.
- **The run-to-run spread is as large as the gaps.** `gpt-5.6-terra` on D1 scored 5, 3 and 5 in three rounds on a task that did not change in substance; on D5, 3, 3 and 4. A cell of five is too few to rank these two models on these tasks.
- **The traps do bite, sometimes.** Across the three rounds a large model answered D1 with the complaints once, D5 with an empty cohort three times, and D4 with the prompt commit until the data ruled it out.

