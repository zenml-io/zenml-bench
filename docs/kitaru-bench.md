# Kitaru Bench: what we run, and why it's hard

*Last checked against the repository: 2026-11-23 (Kitaru 0.27.7, task set v0.1). Pass rates are not on this page; they are in [`kitaru/README.md`](../kitaru/README.md#results).*

We build five fictional companies whose AI agents have weeks of recorded history in a real Kitaru server, with problems planted on known days. Then we hand a coding agent the job a colleague would hand it on a bad week: "this check is wrong", "refunds look too large", "import last night's traces", "replay these against the fix, but don't pay anyone again". A hidden grader scores 1 or 0 by reading what Kitaru recorded, or by running the code the agent left behind on inputs it never saw.

This page covers every world and every task. The sister page for the ZenML set is [`zenml-bench.md`](zenml-bench.md). How to build a task is in [`kitaru/DEVELOPING.md`](../kitaru/DEVELOPING.md).

## The short version

| | count | what it means |
|---|---|---|
| worlds | 5 | fictional companies, each one image section reused by many tasks: `storefront`, `clinic`, `exports`, `helpdesk-live`, `helpdesk-services` |
| tasks | 37 | one instruction each, a reference solution, alternatives, shortcuts that must fail, a hidden grader |
| families | 5 | Checks (8), Diagnosis (10), Import (7), Replay (8), Setup (4) |
| harder variants | 5 | `c1h`, `c7`, `d8h`, `i3h`, `i4h`: built because both large models passed the originals every time |

- **What makes a task hard is a trap, not an obscure API.** Each task has an obvious answer that is wrong: a release that rolled out on the same days a cost rose, a "failure" that is correct behaviour, a fix that works for euros and breaks yen, a replay that silently pays every customer again.
- **No model wrote the history.** Each world is one Python script (`story.py`) that plans every conversation from a random seed. So the right answer to every task is known exactly, down to the session id, and it is written to the grader's answer key, never into the image.
- **Two of the worlds really run.** In `helpdesk-live` and `helpdesk-services` the recorded agent is a real PydanticAI agent with a deterministic stand-in for the model. Its refunds go to a small finance service that writes every payment to a file the agent cannot touch. "Did the agent pay anyone again?" is therefore a row count, not a judgement.

## How a run works

Every task runs in one container. The container holds the whole company: PostgreSQL, the Kitaru server, a Kitaru worker, the company's repository, and the agent under test.

![How one Kitaru Bench attempt runs](charts/kb-how-a-run-works.svg)

A few details that make the numbers trustworthy:

- **The agent is not root.** It runs as user `agent` and reaches Kitaru only over HTTP (`http://127.0.0.1:8000`). It cannot open the database or the grader's files.
- **Nothing starts by itself.** Harbor's healthcheck runs `/opt/kitaru-bench/start.sh` until it succeeds. The script starts Postgres, the server and one worker (`bench-worker`, as user `agent`). It picks a fresh database password every time, so nothing from the build can log in later.
- **The network is closed except for the model provider.** Every task allows only `api.anthropic.com`, `api.openai.com` and `chatgpt.com`. There is no PyPI. Kitaru's built-in plugins are pre-downloaded as wheels and the docs are in `/opt/kitaru-docs`.
- **Code the agent registers runs during grading, safely.** If the agent writes an evaluator or importer, the grader runs it. Before that, `start_grader_worker()` makes `/tests`, `/solution` and `/logs` readable by root only, kills every process the agent left, and starts a fresh worker as a third user, `grader`. Every such task ships a `read_grader_labels.sh` shortcut that tries to open the answer key; it must score 0.
- **Runs go to Modal.** Harbor's local Docker environment refuses the network allow-list, so tasks run with `--env modal`. Modal builds the image from `environment/Dockerfile`, which is why its `FROM` names the published base image on Docker Hub. Prime's runner never builds a Dockerfile; it uses prebuilt per-task images made by `kitaru/scripts/build_on_modal.py`.
- **Four checks before a task counts:** the reference solution scores 1 five times out of five, doing nothing scores 0, every shortcut in `tests/shortcuts/` scores 0, and a second, different valid solution scores 1.

### The answers the grader reads

Most tasks end in something Kitaru stores, so the grader never has to parse prose:

| answer type | what the agent leaves | how the grader reads it |
|---|---|---|
| cohort | a named set of sessions | precision and recall against the answer key; both must be at least 0.9; the newest cohort version counts |
| investigation | linked sessions with verdicts (`problematic` / `acceptable`) | the exact links and verdicts |
| evaluation results | verdicts from an evaluator, stored per session | coverage and correctness per session, plus caps on how much was run |
| registered code | an evaluator, importer or agent version | the grader's worker runs it on hidden sessions, logs or requests |
| `answer.json` | a cause category, a commit id, a date | exact match, next to the cohort |
| finance and order records | rows the services wrote | counted before and after; one new refund row means someone was paid |

## Worlds and their tasks

### `storefront`: Larkspur Goods returns assistant (15 tasks)

An online shop's returns assistant, `returns-agent`, with two tools: `lookup_order` and `issue_refund`. Sixty days of history, 1 June to 30 July 2026, three releases.

There are two versions of this history:

- **Base history** (2,997 sessions), used by C1 to C7. Only standing problems are planted: confirmation replies in euros that quote 100 times the refund, conversations with too many order lookups, late refunds, double refunds, curt replies with no closing courtesy, and idle timeouts (the customer never came back, which is fine).
- **Diagnosis history** (3,117 sessions), used by C1h, D6, D7, D8, D8h and D9. The same history plus four dated problems. The C tasks' images do not change when a diagnosis problem is added, because the extra problems are drawn from a second random stream.

![storefront timeline of releases and planted problems](charts/kb-storefront.svg)

What is planted, in numbers (base / diagnosis history):

| problem | what happens | sessions |
|---|---|---|
| euro reply ×100 | from 1.4.0, euro refunds to a card quote 100× the amount in the reply; the money refunded is right; store credit is unaffected | 182 / 195 |
| repeated lookups | more than 3 `lookup_order` calls | 131 / 135 |
| idle timeout | no closing courtesy because the customer left; nothing wrong | 143 / 144 |
| curt reply | ended normally with no closing courtesy | 19 |
| late refund | refunded more than 30 days after delivery (28–30 days is allowed) | 27 / 30 |
| double refund | refunded twice in one conversation | 17 |
| over-refund *(diagnosis)* | 15–28 June: about 1 full refund in 7 also pays a shipping fee | 49 in D6's key (38 fee cases plus double refunds over the total) |
| cost spike 1 *(diagnosis)* | 21 June 10:00–20:00: order service down, 4–6 extra timed-out lookups per conversation | 32 |
| cost spike 2 *(diagnosis)* | 4 July: `summer-sale` promotion, 120 extra conversations of ordinary cost | 120 |
| model swap *(diagnosis)* | 9 July 14:00 to 18 July: the provider served `gpt-5.4-mini-2026-07-08` while the request said `gpt-5.4-mini`; model calls about 2.2× slower; no release | 355 |

Also in the store: a cohort `reviewed-july` of 40 conversations, each with a human reviewer's verdict and explanation, and three registered evaluators. `polite-closing` passes only if the reply contains one of three closing phrases, so it wrongly fails idle timeouts. `refund-issued-once` has two versions (v2 counts only refund calls that succeeded). The workspace holds the evaluators' source and `checks.txt`, the team's release checks.

| task | history | what the agent is asked | why it's hard | graded on |
|---|---|---|---|---|
| `c1-rule-from-builtins` | base | give every conversation from 24 July a verdict on "at most 3 order lookups", with a built-in evaluator | the week has 359 conversations and Kitaru evaluates 100 per request; the obviously named built-in only describes and leaves `passed` empty; "more than three" is easy to encode as a maximum of two; running it wider than the week fails | stored evaluations: right on all 359, at most 50 older sessions evaluated |
| `c1h-two-rules-from-builtins` | diagnosis | as C1 over 9–15 July, plus "every model call served by exactly `gpt-5.4-mini`", a different built-in per rule | the obvious model-match built-in treats the dated variant as a "hold", not a failure, so the 210 swapped sessions get no verdict | stored evaluations: both rules right on all 345 sessions |
| `c2-finding-to-check` | base | write and register an evaluator that fails conversations whose reply quotes 100× the refund | the history suggests "euro + card + after 1.3.0", but the hidden set adds store credit, a new release 1.5.0, yen, and correct partial refunds where the order total is exactly 100× the refund | the latest version, run by the grader on 120 hidden sessions: precision and recall ≥ 0.9 |
| `c3-evaluator-is-wrong` | base | `polite-closing` fails 1 conversation in 20: decide whether the assistant or the check is wrong, register a corrected version | most failures are idle timeouts; "let questions pass", "let long replies pass" and "judge only refunds" all misjudge some curt replies | version ≥ 2 on 120 hidden sessions: precision and recall ≥ 0.9 |
| `c4-backfill-one-release` | base | evaluate every conversation of release 1.4.1 with `refund-issued-once@2`, nothing earlier | 464 sessions against a 100-per-request limit, with caps: at most 30 older sessions, at most 1,400 results | stored evaluations and the caps |
| `c5-agree-with-reviewers` | base | write an evaluator that agrees with the 40 human reviews, and with conversations nobody reviewed | two rules have to be inferred from the explanations (refund after 30 days; wrong amount in the reply); day 30 is allowed, and the hidden set is full of day-30 cases | 120 hidden sessions: precision and recall ≥ 0.9, and ≥ 0.9 agreement on the 40 |
| `c6-check-before-merge` | base | write `bin/check.sh <cohort>`: run the team's checks on every member, exit 0 if ≥ 90% pass, 1 if not, 2 if it can't do its job | hidden cohorts have 130 members (over the limit), and two sit just either side of the bar (92.3% and 87.7%); computing the answer without storing results fails | the script on 4 hidden cohorts with random names: exit codes, and stored results covering every member |
| `c7-fix-check-then-backfill` | base | C3 and C4 in one: fix `polite-closing`, then backfill 1.4.1 with the fixed version under the caps | exploring by running the old check over whole releases blows the result cap | stored results, the caps, then the hidden 120 as in C3 |
| `d6-refunded-too-much` | diagnosis | cohort of every conversation where the total refunded is more than the order cost | the louder euro-reply fault is a decoy (its refunds were right); `>=` catches every full refund; comparing per call misses double refunds | cohort vs 49 |
| `d7-slower-no-release` | diagnosis | cohort of slower conversations, the cause, the first day | the cause shows only in `model` vs `requested_model`; for the first four days only about 35% were affected, so "the whole slow period" and "fully slow days only" both fail | cohort vs 355, cause `served_model_changed`, day 2026-07-09 |
| `d8-six-to-read` | diagnosis | an investigation of 3–6 conversations from the last week that a person should read, each `problematic`, at least 2 kinds | `polite-closing` failures are mostly idle timeouts, which are fine | each link must be a planted mistake |
| `d8h-triage-check-failures` | diagnosis | link exactly the last week's conversations that either check fails, each with the right verdict | idle timeouts need `acceptable`, curt replies and double refunds `problematic`; "a question means the assistant is waiting" is wrong for some curt replies | the exact link set and verdicts |
| `d9-retries-or-traffic` | diagnosis | cost spiked on two days: one cohort and one cause per day | spike 1 is retries, spike 2 is extra traffic at ordinary cost; "the most expensive conversations" works for the first and not the second | cohorts vs 32 and 120, dates, causes `retry_loop` and `traffic_increase` |

### `clinic`: Fernhill Vets appointment assistant (5 tasks)

A veterinary chain's booking assistant, `booking-agent`, with ten tools (search clinics, check availability, book, reschedule, register owners and pets, and more). Ten clinics in three towns. 3,211 conversations from 1 June to 20 July 2026, three releases, and a git repository whose five commits are dated to match the history. All five D tasks share one image.

The point of this world is that **several things change at once, and most of them are not the cause.** A release rolls out the same week cost rises. A commit lands the day before failures rise. The diagnosis tasks ask which change explains which symptom.

![clinic timeline of releases, commits and planted problems](charts/kb-clinic.svg)

The story, in order:

1. **15 June.** The scheduling service starts booking Harbour Street into Harbour Square, and Mill Road into Millbrook Road, about 7 times in 10. The assistant's reply still names the clinic the customer asked for, so the reply text looks right. Search also lists the neighbouring clinic first, so the assistant searches twice.
2. **From 17 June**, 13 customers complain. These are later conversations, not the bad bookings themselves.
3. **21–25 June.** Release 1.2.0 ("shorter greeting") rolls out: 20%, 40%, 60%, 80%, then everything. Its conversations cost the same as 1.1.0's.
4. **From 22 June**, a partner portal sends about 7 new patients a day. Registering a new patient takes about 3 times as many model calls, so cost per conversation goes from 0.000809 to 0.001108. The release is a decoy for this rise.
5. **27 June.** A litter check-up offer goes out (prompt commit on 26 June). Customers try to book 4–7 animals, and booking refuses with 422 because the limit is 3. The share of conversations with a failed call goes from 1.7% to 5.5%. Nothing is broken: the limit is old.
6. **1 July 08:05.** A config commit cuts `max_tokens` from 400 to 120 to bring latency down. No release. Long replies (care advice, new-patient summaries) now stop mid-sentence: 288 conversations with `finish_reason: length`.
7. **9 July.** Release 1.3.0 asks the clinic search for the exact match first. The double search stops. The wrong-clinic bookings do not: 98 more happen under 1.3.0.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `d1-wrong-clinic` | cohort of every booking made at a clinic other than the one asked for | the reply names the right clinic, so text search finds nothing; the fault is only in `book_appointment`'s result; the 13 complaints are a decoy | cohort vs 269 |
| `d2-was-it-the-release` | cohort of the conversations behind the cost rise, and the cause | release 1.2.0 rolled out on exactly those days but costs what 1.1.0 did | cohort vs 207, cause `traffic_mix_changed` |
| `d3-answers-cut-off` | cohort of cut-off conversations, the commit and the first day | no release went out; the newest commit (1.3.0) is a decoy; reverting the config breaks the "don't change the repo" rule | cohort vs 288, the config commit, day 2026-07-01 |
| `d4-what-broke` | cohort of the failures behind the rise, and the cause | nothing is broken: customers started asking for group bookings, which an old rule refuses; "outage" and "the prompt commit broke it" both fail | cohort vs 67, cause `expected_rejection` |
| `d5-did-the-hotfix-work` | cohort of wrong-clinic bookings under 1.3.0; empty is a legal answer | 1.3.0 removed the visible symptom (the double search), so "it worked, leave it empty" is tempting and wrong | cohort vs 98 |

### `exports`: Tidewater Couriers (7 tasks)

A courier company with two assistants and **no recorded history in Kitaru yet**. The tasks are about getting traces from elsewhere into Kitaru correctly.

- **Dispatch assistant** (`dispatch-agent`) writes a home-made JSONL log described in `docs/trace-format.md`. The log is messy in realistic ways: conversations interleave, some lines are truncated, some conversations never write an `end` line, a tool call (`plan_route`) makes another tool call (`geocode`), and cost is in millionths of a dollar.
- **Support assistant** (`support-assistant`) was traced with Langfuse. A support ticket has 1–4 turns, and each turn is one Langfuse trace. Langfuse's `sessionId` is the chat-widget visit, not the ticket: 30% of tickets share a visit, and a ticket can continue in a new visit. The ticket id is only in `metadata.ticket.id`.

The nightly-import tasks (I4, I4h) start from a store an earlier script damaged:

![exports nightly import timeline](charts/kb-exports-nightly.svg)

Each night's file holds the day before and the day itself, so a correct script must recognise tickets it has already imported. The v2 script named the source after the file, so Kitaru treated nights 6 and 7 as new tickets. The 48 tickets of days 6 and 7 exist only as those strays.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `i1-import-an-export` | import a Langfuse export of 90 tickets for a new agent with two releases, under the right source identity | without a source identity every ticket fails while the CLI still reports success; the release is per trace and about 12% of tickets move between releases | the sessions Kitaru holds vs the export: tickets, version, call counts, cost |
| `i2-one-ticket-one-session` | write a script that imports a Langfuse export as one session per whole ticket, with no monitoring probes | the default import groups by `sessionId`, the widget visit, which mixes and splits tickets | the given export, then the script run on a hidden export |
| `i3-write-an-importer` | write and register an importer `tw-trace` for the home-made log | interleaving, broken lines, missing `end` (the session must be `failed`), tool under tool, a missing `cached` key, cost units | a 150-conversation hidden log through the latest version, compared node by node |
| `i3h-messy-log` | as I3, on a messier log | batch calls carry no cost (compute it from the price table), about 3% of lines are written twice, model calls sit under tools, and the hidden log uses ISO times with UTC offsets the sample never shows | a hidden log, as I3 |
| `i4-nightly-import-twice` | fix the nightly script and repair the store: each ticket exactly once, the existing sessions kept as the same objects, the reviewed cohort untouched | wiping and re-importing kills the reviewed sessions; deleting only the strays loses the 48 tickets that exist only as strays | the store vs the files and a snapshot, then the script run twice on night 8 |
| `i4h-strays-at-scale` | as I4, plus `bin/remove_strays.sh` | the grader's store holds about 1,900 sessions: more than one page of any listing | I4's checks, then the script on 500 strays and 1,200 good sessions |
| `i5-invoice-does-not-match` | Kitaru's August cost is a third below the provider's bill: fix the importer and get August right | two defects: model calls under tool calls are dropped (31.7% of the cost) and cached tokens are ignored; Kitaru skips ids it already has, so re-importing without deleting changes nothing | August's 450 sessions vs the log, then a hidden log; version 1 must still exist |

### `helpdesk-live`: a helpdesk agent that really runs (4 tasks)

A real PydanticAI agent, `helpdesk-agent`, recorded through Kitaru's adapter while the image is built. Its "model" is a Python function (`planner.py`), so the same request always produces the same conversation, and replaying it is meaningful.

The agent has six tools. Four read local JSON files (orders, customers, return policy, shipping). Two, `issue_refund` and `escalate_to_human`, call a **finance service** on port 8091. That service writes every refund and escalation to a file only root can read.

![What a replay does with each tool call](charts/kb-replay.svg)

> **Why the finance service matters.** When Kitaru replays a recorded conversation, its tool policy decides, per tool, whether to answer from the recording or call the real tool. The default is live. So a replay with the default policy calls `issue_refund` for real, and the finance service writes a new row: a customer was paid twice. Every replay task checks that the finance file did not grow.

History: 260 requests. REQ-0001 to 0200 ran on release 1.6.0, REQ-0201 to 0260 on 1.6.1 (which only adds the last-scan time to status replies). 58 refunds (19 in euros), 36 escalations. A cohort `refunds-to-recheck` holds 32 non-euro refunds from 1.6.0.

The planted bug: `money.to_major` divides by 100 for dollars and pounds only. Euros pass through, so euro refunds are 100× too large. Yen is already right, because yen has no minor unit. That is why "divide everything by 100" fixes euros and breaks yen.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `f1-replay-without-refunding` | replay the 32-session cohort against version 2, without paying anyone again | the default tool policy runs the live tools, which pays all 32 again | completed replays per member that reach `issue_refund`; finance row count unchanged |
| `f2-fix-euro-with-evidence` | fix the currency bug in a new release 1.6.2, and prove it with an experiment that pays nobody | an all-recorded policy fails, because the fixed refund amount is not in the recording; no policy pays everyone; "divide by 100" breaks yen and stays hidden if the experiment has no yen | releases untouched, experiment evidence, finance unchanged, then 24 hidden requests in four currencies replayed against the fix |
| `f3-refunds-far-too-large` | symptom only, "some refunds are far too large": find the bug and release a fix without paying anyone | running the agent by hand to test pays real refunds; the obvious fix breaks yen | as F2, without the experiment requirement |
| `f4-experiment-keeps-failing` | an experiment of the fixed release fails every time: get a completed run without letting the refund tool run live | the 19 euro refunds now have different arguments, so the recording has no answer for them; `passthrough` pays them; an experiment with runs cannot change its policy (409), so a new one is needed | a completed run over all 58, no live refund tool, finance unchanged |

### `helpdesk-services`: the same assistant, release 2.0.0 (8 tasks)

The helpdesk agent a release later (2.0.0), now reading orders from an **order service** on port 8092 instead of local files. That service is deliberately awkward: each answer takes 0.25 s, it serves at most 4 requests at a time and refuses a fifth with 429, and it logs every request to a root-only file the grader reads. The finance service is the same as in `helpdesk-live`.

History: 420 requests, all on version 1: 225 refunds, 114 status questions, 81 disputes; 98 refunds paid, 81 escalations.

Planted: **seven places where the planner asks the same thing twice.**

| repeat | does the second answer ever differ? |
|---|---|
| order with several items read again in a status request | never |
| customer read again before escalation | never |
| policy checked again before a refusal | never |
| retry after a timeout | always |
| second ask for a parcel showing `label_created` | always |
| re-read before paying (`credit_lands`) | rarely: 6 recorded cases |
| out-for-delivery parcel asked again (`arrives_now`) | rarely: 4 recorded cases |

At `reasoning_effort: low` the planner skips every second ask, answers disputes itself and skips the guest account lookup. 96 recorded conversations end differently at low effort: the 81 disputes plus 15 others. F8 uses a variant history in which 67 requests say "refund only the <item>", and release 2.0.0 refunds the whole order for those.

| task | what the agent is asked | why it's hard | graded on |
|---|---|---|---|
| `f5-stop-asking-twice` | remove the second asks that never returned anything new, keep the ones that did | two of the seven differ only in a handful of cases, so judging from a sample removes them; testing by hand pays | hidden requests through 2.0.0 and the new version: same answers and payments, lookups = 2.0.0's minus exactly the three wasteful repeats |
| `f6-run-them-together` | let independent lookups run concurrently, without changing a call or an answer | recorded messages mention at most 2 orders, hidden ones up to 6, and the service refuses a fifth concurrent request: "everything at once" passes on the recordings and fails hidden | same calls and answers, lookups overlap, many-order messages take at most 0.75× the time, no 429 |
| `f7-where-low-effort-is-safe` | cohort of conversations that end the same at low effort, proved with an experiment that overrides the model parameters and pays nobody | reading the planner says "all but disputes", but 15 non-disputes also differ, and they show only when every conversation is replayed against its own recording | cohort vs the 324 safe conversations (≥ 95%, none wrong), a completed experiment with the override |
| `f8-pick-between-two-fixes` | two colleagues' fixes for one-item refunds: run both on one fair cohort, release the better one | Ana's fix passes her own 24 hand-picked conversations but is wrong when quantity > 1 or there's a discount; Ben's fix is right, but his run fails because it calls a new read-only tool the recordings don't have | the evidence, then hidden requests through the released version: amounts paid = amounts owed |
| `o1-nothing-is-running` | no worker runs and the team's start script claims the wrong work: fix it | an explicit `--claim` replaces the defaults, so adding one claim drops the others; it must take replays for future versions too, and never imports | the grader starts the worker with the script and checks what it claims within 5 minutes, and that an import stays pending |
| `o2-record-this-agent` | record an unrecorded PydanticAI agent under `parcel-chaser`, and register a version that replays | it is built in two places and started two ways, so wrapping one entrypoint leaves the other unrecorded; the registered command must take the order the worker passes | both entrypoints on hidden orders, then replays with every tool answered from the recording and zero order-service requests |
| `o3-make-it-replayable` | recorded conversations can't be replayed: fix it without touching the planner or tools | four causes, each visible only after the one before is fixed: no replay capabilities declared, another host's directory, an entrypoint that needs an argument, and an environment variable only the shell script sets | hidden and recorded conversations replayed with a low-effort override; all complete; nobody paid |
| `o4-record-a-langgraph-agent` | record a LangGraph agent with Kitaru's LangGraph adapter, replayable | wrapping the compiled graph records every run but can't answer tools from a recording; only the adapter's factory path can, and it refuses `stream()`, so the reading code must change while the output stays the same | as O2, one entrypoint |

## Where things live

| what | where |
|---|---|
| base image (Postgres, Kitaru, agent CLIs, wheels, docs) | `kitaru/base/`; published as `zenmldocker/kitaru-bench-base`, pinned by digest in `kitaru/base/IMAGE` |
| a world: story, loader, workspace | `kitaru/worlds/<world>/` (`story.py`, `load.py`, `Dockerfile.world`, `workspace/`) |
| a task | `kitaru/tasks/<id>/` (`instruction.md`, `task.toml`, `world`, optional `plants`, `setup/`, `workspace/`, `solution/`, `tests/`) |
| the generated image recipe | `kitaru/tasks/<id>/environment/`, written by `kitaru/scripts/sync_env.sh`; never edit by hand |
| the answer key | `kitaru/tasks/<id>/tests/fixtures/ground_truth.json`, written by `sync_env.sh` |
| grader helpers | `kitaru/checks/kitaru_checks.py`, copied into each task's `tests/` |
| decisions and spike results | `docs/decisions.md`, entries from 2026-11-20 on |
| failures read from transcripts | `results/kitaru-level1.md`, `kitaru-level2.md`, `kitaru-level3.md` |
