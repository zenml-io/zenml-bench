# Kitaru Bench

37 tasks in which a coding agent (Claude Code, Codex, Terminus 2, …) has to get real work done with **real [Kitaru](https://kitaru.ai)**, pinned to version 0.27.7. Kitaru records what AI agents do: every conversation, model call and tool call. The tasks are the jobs a team has once those records exist: check them, find what went wrong, bring in traces from elsewhere, replay a run against a fix.

Every task is graded on **what Kitaru recorded**, never on what the agent says it did. Where the agent leaves code behind (an evaluator, an importer, a fixed agent), the grader runs that code on inputs the agent never saw.

The tasks are in [Harbor](https://www.harborframework.com) format, so the same set runs as an evaluation and, through the Prime Intellect wrapper, as a training environment.

## Run it

The tasks ask for a network allow-list, which Harbor's local Docker environment does not enforce, so run them on [Modal](https://modal.com) (`uv tool install 'harbor[modal]'`, then `modal setup`). Model keys go in `.env`.

```bash
# the whole set, one attempt per task
harbor run -d zenml/kitaru-bench@v0.1 --env modal -a claude-code -m claude-sonnet-5-5 --env-file .env

# one task
harbor run -d zenml/kitaru-bench@v0.1 -i "*c2-finding-to-check" --env modal -a codex -m gpt-5.6-terra --env-file .env

# the reference solutions, no model needed
harbor run -d zenml/kitaru-bench@v0.1 --env modal -a oracle
```

Without a Harbor Hub account, the same tasks resolve from the repository: add `--repo zenml-io/zenml-bench@kitaru-v0.1` and name the dataset `kitaru-bench@0.1.0`.

## What a task looks like

The agent lands in a container as an ordinary user. Kitaru is already running there (PostgreSQL, the Kitaru server, a worker), loaded with the history of a fictional company. The agent has the Kitaru CLI, the Python SDK and the docs, offline. It reads `instruction.md`, which states a problem the way a colleague would, and gets to work.

Each task passed four checks before it was counted:

1. the reference solution scores 1, five times out of five
2. doing nothing scores 0
3. every plausible shortcut we could think of scores 0 (they are in each task's `tests/shortcuts/`)
4. a second, different valid solution scores 1

## The five companies

| world | what it is |
|---|---|
| `storefront` | an online shop's returns assistant, about 3,000 recorded conversations |
| `clinic` | a veterinary chain's booking assistant, 3,211 conversations and a repository with dated commits |
| `exports` | a courier company with two assistants: one writes a home-made trace log, one was traced with Langfuse |
| `helpdesk-live` | a helpdesk agent that really runs, with a finance service that records every refund |
| `helpdesk-services` | the same agent one release on, with an order service that is slow and counts every lookup |

No model was called to build a history: each world is one script that plans every conversation from a seed, so the answer to every task is known exactly.

## Task families

| family | tasks | what the agent does |
|---|---|---|
| Checks | 8 | apply a rule with a built-in evaluator, write or repair an evaluator, backfill one release, write a pre-merge check script |
| Diagnosis | 10 | find every conversation a problem affected and record the answer as a Kitaru cohort or an investigation, past a decoy (a release that rolled out the same days, complaints that are not the affected cases, a "failure" that is correct behaviour) |
| Import | 7 | import an export from another tracing tool, write an importer for a home-made log, repair a nightly import and the store it damaged |
| Replay | 8 | replay recorded runs of an agent that really runs against a fix, without repeating side effects such as refunds; prove a fix with an experiment |
| Setup | 4 | get a worker claiming the right work, record an unrecorded agent (PydanticAI, LangGraph), make recorded runs replayable |

## Results

Passes out of 5 attempts, with nothing but the CLI, the SDK and the docs (no skills, no MCP server). Run on 20 and 21 November 2026.

| model | harness | passed |
|---|---|---|
| `claude-sonnet-5-5` | Claude Code | 171 of 185 |
| `gpt-5.6-terra` | Codex | 170 of 185 |
| `gpt-5.4-mini` | Codex | 13 of 185 |

Five attempts per cell is a small sample: 5/5 against 4/5 is not a meaningful gap, and the two large models cannot be ranked from this table.

| task | family | world | sonnet-5.5 | gpt-5.6-terra | gpt-5.4-mini | what it asks |
|---|---|---|---|---|---|---|
| `c1-rule-from-builtins` | Checks | `storefront` | 5/5 | 5/5 | 0/5 | Check a tool-call limit on one week of recorded conversations with one of Kitaru's built-in evaluators, and nothing wider. |
| `c1h-two-rules-from-builtins` | Checks | `storefront` | 5/5 | 5/5 | 1/5 | Harder variant of C1: two rules checked with two built-in evaluators over one week; the obvious parameter for the second rule leaves the rule breakers without a verdict. Graded on the evaluations Kitaru holds. |
| `c2-finding-to-check` | Checks | `storefront` | 5/5 | 4/5 | 0/5 | Refund confirmations in euros quote 100 times the refunded amount. Write and register a Kitaru evaluator that fails exactly those conversations; it is run on conversations the agent never saw. |
| `c3-evaluator-is-wrong` | Checks | `storefront` | 5/5 | 5/5 | 1/5 | A registered politeness evaluator fails one conversation in twenty. Work out whether the assistant or the evaluator is at fault and register a corrected evaluator version; it is run on conversations the agent never saw. |
| `c4-backfill-one-release` | Checks | `storefront` | 5/5 | 5/5 | 3/5 | Evaluate every conversation served by one release with the corrected version of an existing evaluator, and no earlier conversations. |
| `c5-agree-with-reviewers` | Checks | `storefront` | 3/5 | 0/5 | 0/5 | Forty conversations carry human review verdicts. Write and register an evaluator that agrees with the reviewers there and on conversations nobody reviewed; it is run on conversations the agent never saw. |
| `c6-check-before-merge` | Checks | `storefront` | 1/5 | 1/5 | 0/5 | Write a script that runs the team's release checks on a Kitaru cohort and exits non-zero when too few conversations pass; it is run on cohorts the agent never saw. |
| `c7-fix-check-then-backfill` | Checks | `storefront` | 5/5 | 5/5 | 0/5 | Harder variant of C3 and C4 in one: decide whether a check is wrong, register a corrected version, and backfill one release with it under a cap on results; graded on what Kitaru stored and on a hidden run. |
| `d1-wrong-clinic` | Diagnosis | `clinic` | 4/5 | 5/5 | 0/5 | Build the cohort of every booking that was made at a clinic other than the one the customer asked for; the customers who complained are a different, small set. |
| `d2-was-it-the-release` | Diagnosis | `clinic` | 5/5 | 5/5 | 0/5 | Cost per conversation rose as a release rolled out: build the cohort of the conversations that account for the rise and name the cause; the release is a decoy. |
| `d3-answers-cut-off` | Diagnosis | `clinic` | 5/5 | 5/5 | 0/5 | Longer answers stop mid-sentence and no release went out: build the cohort of cut-off conversations, and name the commit and the first day. |
| `d4-what-broke` | Diagnosis | `clinic` | 3/5 | 5/5 | 0/5 | More conversations contain a failed tool call: build the cohort of the failures that account for the increase and name the cause. Nothing is broken. |
| `d5-did-the-hotfix-work` | Diagnosis | `clinic` | 5/5 | 4/5 | 0/5 | Release 1.3.0 was meant to stop wrong-clinic bookings: build the cohort of the ones that still happened under it. An empty cohort is a legal answer and the wrong one. |
| `d6-refunded-too-much` | Diagnosis | `storefront` | 3/5 | 5/5 | 0/5 | Build the cohort of every conversation in which the assistant refunded more than the order cost. |
| `d7-slower-no-release` | Diagnosis | `storefront` | 5/5 | 4/5 | 0/5 | Replies got slower for a while with no release. Build the cohort of affected conversations, name the cause and the first affected day. |
| `d8-six-to-read` | Diagnosis | `storefront` | 5/5 | 5/5 | 0/5 | Open an investigation over at most six of last week's conversations that a person should read, each with a verdict. |
| `d8h-triage-check-failures` | Diagnosis | `storefront` | 5/5 | 5/5 | 0/5 | Harder variant of D8: link every conversation of the last week that one of the team's two checks fails, and say for each whether the check is right; graded on the investigation Kitaru holds. |
| `d9-retries-or-traffic` | Diagnosis | `storefront` | 4/5 | 4/5 | 0/5 | Model cost spiked on two separate days. One cohort and one cause per day. |
| `f1-replay-without-refunding` | Replay | `helpdesk-live` | 5/5 | 5/5 | 1/5 | Replay a cohort of recorded refunds against a newer release without paying anyone again; graded on the replays Kitaru holds and on the finance service's own record. |
| `f2-fix-euro-with-evidence` | Replay | `helpdesk-live` | 5/5 | 5/5 | 0/5 | Fix a currency fault in a runnable agent, register the fix as a new version, and prove it with an experiment that pays nobody; then hidden conversations are replayed against the fix. |
| `f3-refunds-far-too-large` | Replay | `helpdesk-live` | 5/5 | 5/5 | 3/5 | Symptom only: some refunds are far too large. Find the currency fault and fix it in a new release without paying anyone; hidden conversations in every currency are replayed against the fix, and the obvious fix breaks yen. |
| `f4-experiment-keeps-failing` | Replay | `helpdesk-live` | 5/5 | 5/5 | 0/5 | An experiment of a fixed release fails every time: the fix changes a tool call's arguments, so the recording has no answer for it. Get a completed run without letting the refund tool run live. |
| `f5-stop-asking-twice` | Replay | `helpdesk-services` | 5/5 | 5/5 | 0/5 | A runnable agent asks its services for the same thing twice in seven places. Remove the second asks that never returned anything new in 420 recorded conversations and keep the ones that did, two of them only a handful of times; hidden requests check the lookups made and the answers. |
| `f6-run-them-together` | Replay | `helpdesk-services` | 5/5 | 4/5 | 0/5 | A runnable agent asks its services one thing at a time. Let independent lookups run together without changing a call or an answer; hidden messages ask about up to six orders, and the order service refuses a fifth request at a time, which never happens with the two orders a recorded message holds. |
| `f7-where-low-effort-is-safe` | Replay | `helpdesk-services` | 4/5 | 5/5 | 0/5 | Find the recorded conversations of a runnable agent that end the same way at a cheaper reasoning effort, as a cohort, and prove it with an experiment that overrides the model parameters and pays nobody. Fifteen of the 96 that end differently are not disputes and show only when everything is replayed. |
| `f8-pick-between-two-fixes` | Replay | `helpdesk-services` | 5/5 | 5/5 | 0/5 | Two candidate fixes for refunds of one item, each with its author's own experiment: one passes on 24 hand-picked conversations, the other's run fails on a tool the recordings do not have. Run both over one cohort of every such refund, release the one that is right more often; hidden requests check the amounts. |
| `i1-import-an-export` | Import | `exports` | 5/5 | 5/5 | 0/5 | Import a Langfuse export into Kitaru for a new agent with two releases, under the right source identity; graded on the sessions Kitaru holds. |
| `i2-one-ticket-one-session` | Import | `exports` | 5/5 | 5/5 | 1/5 | Write a script that imports a Langfuse export so that one Kitaru session is one whole ticket; graded on the given export and on a hidden one run through the script. |
| `i3-write-an-importer` | Import | `exports` | 5/5 | 5/5 | 0/5 | Write and register a Kitaru importer for an in-house trace log format; graded by importing a hidden log through it. |
| `i3h-messy-log` | Import | `exports` | 5/5 | 5/5 | 1/5 | Harder variant of I3: the log has batch calls with no cost, repeated lines, model calls under tool calls, and a second timestamp form that the sample never shows; graded by importing a hidden log. |
| `i4-nightly-import-twice` | Import | `exports` | 5/5 | 5/5 | 0/5 | Repair a nightly Langfuse import script that began creating duplicate sessions, and repair the store without losing the sessions that were right; graded on the store and on two runs of the script on a hidden file. |
| `i4h-strays-at-scale` | Import | `exports` | 4/5 | 4/5 | 0/5 | Harder variant of I4: the same repair, plus a script that removes stray sessions and is graded on a store of about 1,900 sessions, more than one page of any listing. |
| `i5-invoice-does-not-match` | Import | `exports` | 5/5 | 5/5 | 0/5 | Kitaru's cost for a month is a third below the provider's bill: find the importer defects, register a corrected version and get the month right in Kitaru; graded on the month and on a hidden log. |
| `o1-nothing-is-running` | Setup | `helpdesk-services` | 5/5 | 5/5 | 0/5 | No worker runs, work is waiting, and the team's start script claims the wrong work: one pinned agent version and imports, no evaluations. Fix the script; the grader starts the worker with it and asks for evaluations, replays against a version registered afterwards, and an import the worker must leave alone. |
| `o2-record-this-agent` | Setup | `helpdesk-services` | 5/5 | 5/5 | 0/5 | A PydanticAI agent runs unrecorded, built in two places and started two ways. Record every run under a named Kitaru agent and register a version that replays; the grader runs both entrypoints on hidden orders and replays the sessions with every tool answered from the recording. |
| `o3-make-it-replayable` | Setup | `helpdesk-services` | 5/5 | 5/5 | 2/5 | Recorded conversations of a runnable agent cannot be replayed: the registered version declares no replay capabilities and points at another host's directory, and the entrypoint needs a message and an environment variable a worker does not supply. Four causes, each visible only after the one before is fixed; hidden conversations are replayed with an override. |
| `o4-record-a-langgraph-agent` | Setup | `helpdesk-services` | 5/5 | 5/5 | 0/5 | A LangGraph agent runs unrecorded and is read with stream(). Record it with Kitaru's LangGraph adapter under a named agent and register a version that replays. Wrapping the compiled graph records every run and cannot answer a tool from a recording; only the adapter's factory path can, and it does not record stream(). |

What each failure was, read from the transcripts: [`results/kitaru-level1.md`](https://github.com/zenml-io/zenml-bench/blob/main/results/kitaru-level1.md), [`kitaru-level2.md`](https://github.com/zenml-io/zenml-bench/blob/main/results/kitaru-level2.md), [`kitaru-level3.md`](https://github.com/zenml-io/zenml-bench/blob/main/results/kitaru-level3.md).

## More

- Source, graders and reference solutions: https://github.com/zenml-io/zenml-bench (`kitaru/`). Solutions and tests are public, as is usual for Harbor task sets.
- Harbor Hub: https://hub.harborframework.com/datasets/zenml/kitaru-bench
- Prime Intellect Environments Hub: https://app.primeintellect.ai/dashboard/environments/zenml/kitaru-bench (`prime env install zenml/kitaru-bench`; wrapper source in `integrations/prime/kitaru_bench/`).
- The sister set on ZenML itself: [Harbor Hub](https://hub.harborframework.com/datasets/zenml/zenml-bench), [Prime](https://app.primeintellect.ai/dashboard/environments/zenml/zenml-bench).
- Building or changing tasks: [`DEVELOPING.md`](https://github.com/zenml-io/zenml-bench/blob/main/kitaru/DEVELOPING.md).
- License: MIT.
