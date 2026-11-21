# Kitaru Level 3: replay tasks, first four (F1 to F4)

Run on 2026-11-21 on Modal (environment `dev`), Harbor 0.26.0, Kitaru 0.27.7, `kitaru-pydantic-ai` 0.4.0, bare condition (CLI, SDK, offline docs; no skills, no MCP), 5 attempts per cell, 30-minute agent limit. Rows: `results/kitaru-<task>-baseline.jsonl`. Raw jobs: `jobs/kbaseline-f*` (not committed).

The world is `helpdesk-live`: a helpdesk assistant that really runs (a PydanticAI agent with a scripted model), 260 conversations recorded through the real adapter, and a finance service that records every refund in a file the agent cannot read. A replay that lets the refund tool run live pays a customer again, and the grader sees the row.

Passes out of 5:

| task | what the agent must do | Claude Code + `claude-sonnet-5-5` | Codex + `gpt-5.6-terra` | Codex + `gpt-5.4-mini` |
|---|---|---|---|---|
| F1 replay without refunding | replay 32 recorded refunds against a newer release; nobody may be paid again | 5 | 5 | 1 |
| F2 fix the euro amounts, with evidence | fix a currency fault in a new release, register it, prove it with an experiment over at least 20 refunds that pays nobody; hidden conversations are then replayed against the fix | 5 | 5 | 0 |
| F3 refunds far too large | symptom only; the same fix, no experiment asked for; the obvious fix breaks yen | 5 | 5 | 3 |
| F4 the experiment keeps failing | a fixed release's experiment fails every time, because the fix changes a tool call's arguments; get a completed run without letting the refund tool run live | 5 | 5 | 0 |
| **total of 20** | | **20** | **20** | **4** |

Spend US$12.48 for 60 trials. No infrastructure exception and no timeout. Median agent time: 0.3 to 3.7 minutes.

## What the failures were

All 16 failures are `gpt-5.4-mini`. Read from each trial's `verifier/metrics.json`.

- **F1, 4 of 5: every customer paid again.** All four failing trials produced 32 completed replays against the right version, and the finance service received 32, 32, 33 and 42 new refunds. The replays were created with no tool policy, which in Kitaru runs the live tools.
- **F2, 5 of 5: the fix is right and the evidence is not.** In every trial the hidden replays are right in all four currencies. One trial ran no experiment. The others ran one that paid 32 customers again, or over a cohort that showed no improvement.
- **F3, 2 of 5:** one release that still refunds euros 100 times too much (0 of 8 hidden euro refunds right); one fix not registered as 1.6.2 from its own directory.
- **F4, 5 of 5:** every trial started more runs with the same policy, or one that still stops on the miss; all failed. None let the refund tool run live.

## Reading

- **The two large models pass everything.** The warnings in Kitaru's own docs ("omitting `--tool-policy` uses the server default and may execute live tools") are enough for them, and neither tried the fix that breaks yen.
- **The small model does the dangerous thing by default.** In F1 it paid customers again in four trials of five while reporting the replays as done. This is the clearest result of the round, and the one a "+ skills" or "+ MCP" condition should be tested against first.
- **Built since:** F5 to F8 and O1 to O4, below.

# Kitaru Level 3, second part: F5 to F8 and O1 to O4

Run on 2026-11-21, same setup as above. F7's agent limit is 45 minutes; the others keep 30. Rows: `results/kitaru-<task>-baseline.jsonl`. Raw jobs: `jobs/kbaseline-{f5..f8,o1..o4}-*` (not committed).

The world is `helpdesk-services`: the same kind of assistant as `helpdesk-live`, at release 2.0.0, with 420 recorded conversations, a finance service that records every refund, and a second service, the order service, that takes a quarter of a second per answer, serves four requests at a time, refuses the fifth, and counts every lookup in a file the agent cannot read.

Passes out of 5:

| task | what the agent must do | Claude Code + `claude-sonnet-5-5` | Codex + `gpt-5.6-terra` | Codex + `gpt-5.4-mini` |
|---|---|---|---|---|
| F5 stop asking twice | the planner repeats a lookup in seven places; remove the repeats that never brought anything new in 420 recordings, keep the ones that did (some did in as few as 3 conversations); graded on hidden requests | 5 | 5 | 0 |
| F6 run them together | make independent lookups run at the same time, with the same calls and answers, without the order service refusing one; graded on hidden requests about as many as six orders | 5 | 4 | 0 |
| F7 where low effort is safe | a cohort of the conversations that end the same way at reasoning effort `low` (324 of 420), with none of the 96 that do not, proved by a completed experiment that pays nobody | 4 | 5 | 0 |
| F8 pick between two fixes | two colleagues' fixes, each with its own flattering or failing experiment; build one fair cohort, run both over it with an evaluator, release the better one | 5 | 5 | 0 |
| O1 nothing is running | repair the script that starts this machine's worker so it does all of this machine's work (also for a version registered later) and leaves imports alone | 5 | 5 | 0 |
| O2 record this agent | wire an unrecorded PydanticAI agent with two entry points into Kitaru so that hidden runs are recorded and replay | 5 | 5 | 0 |
| O3 make it replayable | an agent version whose replays are refused or crash, for four separate reasons; make a replay with a model override and a tool policy complete | 5 | 5 | 2 |
| O4 record a LangGraph agent | the same as O2 for a LangGraph agent, with the `kitaru-langgraph` adapter | 5 | 5 | 0 |
| **total of 40** | | **39** | **39** | **2** |

Spend US$31.40 for 120 trials. No infrastructure exception and no agent timeout. Median agent time: 0.2 to 6.7 minutes, except F7 (13.5 minutes for Sonnet, 16.7 for terra: it replays several hundred conversations).

**A first run of F7 and F8 was thrown away** (30 trials, US$14.45; it gave F7 4/2/0 and F8 2/5/0). Reading the failures showed two instructions that allowed a second honest reading. F8 said "asked for one item" and three Sonnet trials counted "My kettle from order … Please refund it" as such a request. F7 did not say that the assistant's code must stay as it is, or that a replayed tool must answer from that same conversation; terra changed the planner once and once used a history scope that answers from any conversation in the cohort, which hides the ten rarest cases. Both instructions now say these things, both graders check them, and each task has a shortcut script for each reading. The numbers above are from the second run.

## What the failures were

Two large-model failures, both the task working as meant:
- **F6, terra, 1 of 5:** in 4 of 60 hidden requests the new release made a call 2.0.0 does not make. When the order read timed out beside the customer read, it repeated both.
- **F7, Sonnet, 1 of 5:** the cohort holds 307 of the 324 safe conversations, 94.75 in 100 where 95 were asked. The agent worked out the cohort by running the planner's code by hand on the recorded tool results instead of replaying, and its copy disagreed with the real thing on 17 conversations. The experiment it ran afterwards could only confirm the 307 it had kept.

38 small-model failures:
- **F5, 5 of 5:** four releases removed the wrong repeats (between 9 and 35 of 60 hidden conversations lack a lookup they needed); one never registered a version.
- **F6, 5 of 5:** three registered nothing usable (no 2.0.1, or one with no working directory); one registered a release whose lookups still run one after another; one registered a release that hangs, and the grader gave up on it.
- **F7, 5 of 5:** no cohort is both complete and clean (two hold all 96 conversations that end differently), and four of the five experiment runs never completed.
- **F8, 5 of 5:** no fair comparison in any trial: cohorts of 1, 6 or 61 conversations where 37 were asked for, or a run missing for one candidate. One registered no release, one registered a directory that does not exist, two released the worse fix, and one released the right fix after paying 122 customers again.
- **O1, 5 of 5:** every script still claims work for version 1 only, so replays against a later version wait for ever. Two also left evaluations unclaimed.
- **O2, 5 of 5 and O4, 5 of 5:** the hidden runs record nothing. Most often the entry point fails with "Session names no agent and no task to infer one from": the agent wrapped the chaser with Kitaru and never told it which agent the runs belong to. In O4, one kept `stream()`, which the adapter refuses, and one passed a dictionary where the adapter wants its policy object.
- **O3, 3 of 5:** the registered command drops the customer message (two trials), or the working directory still points at a path that does not exist.

In two of these trials the grader crashed instead of writing `metrics.json` (F6 on the release that hangs, F8 on the directory that does not exist). The score of 0 was right in both. Both graders were fixed afterwards: such a run now scores 0 with the reason in `metrics.json` under `run_errors`, and after one conversation hangs for 300 seconds the rest are not started.

## Reading

- **Designing each task hard from the start moved the large models very little:** 39 of 40 each. What costs them a trial is a second-order mistake (an extra call on one path, a prediction used where a measurement was asked), not the Kitaru work.
- **"Find everything in the history" is cheap for a large model.** One bulk read of 420 conversations and a count settles F5 in about a minute. Rare cases in the data do not make a task hard when reading all the data costs nothing.
- **The small model fails the setup tasks completely** (2 of 20 on O1 to O4), and on the same point three times: it does not find out how Kitaru decides which agent a run belongs to.
- **F7 is the only task where time matters:** it takes a quarter of an hour because it replays hundreds of conversations, and it is the only one where a large model swapped the measurement for a prediction.

