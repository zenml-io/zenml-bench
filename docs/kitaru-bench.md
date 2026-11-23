# Kitaru Bench: how it works and what every task tests

*Last checked against the repository: 2026-11-23 (Kitaru 0.27.7, task set v0.1). Live pass rates are in [`kitaru/README.md`](../kitaru/README.md#results); failure notes read from transcripts are in `results/kitaru-level1.md` through `kitaru-level3.md`.*

Kitaru Bench tests whether a coding agent can operate and debug AI agents in production using [Kitaru](https://kitaru.ai)—a server that records every conversation, model call, and tool call an AI agent makes.

We build **five fictional companies** with weeks of realistic recorded history in a real Kitaru server and problems planted on known days. Then we hand a coding agent the kind of job a teammate hands it on a bad week: *"this check is flagging good chats"*, *"cost jumped when release 1.2.0 rolled out—was it the release?"*, *"repair last night's duplicate imports"*, *"fix this currency bug and replay past chats to prove it, without refunding anyone again"*.

A hidden grader scores `1` or `0` from **what Kitaru recorded**, **root-only service logs**, and **re-running the agent's code on inputs it never saw**.

![Kitaru Bench at a glance: 5 worlds x 5 task families (37 tasks)](charts/kb-overview.svg)

This page is the plain-language tour of every world and task. The sister page for the ZenML set is [`zenml-bench.md`](zenml-bench.md). To build or change tasks, see [`kitaru/DEVELOPING.md`](../kitaru/DEVELOPING.md).

## Key Kitaru concepts & task families

Five Kitaru concepts show up across the benchmark:

| concept | plain-English meaning |
|---|---|
| **session** | One recorded conversation (messages, model calls, tool calls, timings, and cost) linked to an agent version. |
| **cohort** | A named, versioned set of sessions—used to group affected chats or define the dataset for an experiment. |
| **evaluator** | A built-in or custom check that inspects sessions and stores pass/fail verdicts (`evaluation results`) in Kitaru. |
| **importer** | A parser that brings external traces (Langfuse exports or custom JSONL logs) into Kitaru as sessions, deduplicating by source identity. |
| **replay & experiment** | Re-running recorded conversations against a new agent version or model setting, governed by a **tool policy** deciding whether each tool answers from the recording or runs live. |

The 37 tasks fall into **5 operational families** (5 of them—`c1h`, `c7`, `d8h`, `i3h`, `i4h`—are harder variants built after frontier models saturated the originals):

- **Checks (`C1`–`C7`, 8 tasks):** Run built-in evaluators, write or repair custom evaluators, backfill one release under caps, and gate merges.
- **Diagnosis (`D1`–`D9`, 10 tasks):** Find every affected conversation and pinpoint the true cause past decoys (coincident releases, complaint chats, expected rejections).
- **Import (`I1`–`I5`, 7 tasks):** Bring Langfuse and custom JSONL logs into Kitaru cleanly, handle messy formats, and repair damaged nightly imports.
- **Replay (`F1`–`F8`, 8 tasks):** Replay a live PydanticAI agent against bug fixes, optimizations, or cheaper model settings without triggering real refunds.
- **Setup (`O1`–`O4`, 4 tasks):** Fix worker claims, instrument unrecorded PydanticAI and LangGraph agents, and make recorded runs replayable.

## Anatomy of a task: `f2-fix-euro-with-evidence`

To see how a Kitaru task works end-to-end, look at **`f2-fix-euro-with-evidence`** (in the `helpdesk-live` world):

- **What the agent gets:** A real PydanticAI `helpdesk-agent` with 260 recorded sessions in Kitaru. Two tools (`issue_refund` and `escalate_to_human`) talk to a live **finance service** on port 8091 that appends every call to a root-only file. The prompt says: *"Euro refunds are 100× too large (42.50 EUR is refunded as 4,250 EUR). Put a fix in `/app/releases/1.6.2`, register it as `1.6.2`, and prove it with a Kitaru experiment over ≥ 20 refund sessions using `refund-amount`—without paying anyone again."*
- **Why naive fixes fail (three traps in one task):**
  1. **Side-effect trap:** Kitaru's default replay tool policy is **`live`**. Running an experiment without overriding the policy calls `issue_refund` for real, the finance file grows, and the attempt scores `0`.
  2. **Recorded-only trap:** Setting every tool to `recorded` also fails—once the bug is fixed, `issue_refund` is called with the *corrected* euro amount, which isn't in the recording.
  3. **Currency trap:** `money.to_major` divides USD and GBP by 100 and forgets EUR—but JPY has no minor unit. A sloppy *"divide everything by 100"* fix passes an experiment with no yen, then fails when the grader replays 24 hidden requests covering all four currencies.
- **How the grader proves it:** It checks Kitaru's registered versions and experiment results, confirms the root-only finance file did not gain a single row, and replays 24 unseen multi-currency requests against `1.6.2`.

![What a replay does with each tool call: recorded vs live](charts/kb-replay.svg)

---

## The five worlds and their 37 tasks

No LLM generated the seeded histories: each world is a deterministic Python script (`story.py`) driven by a fixed seed, so every ground-truth session ID is known exactly and written only to the grader's hidden answer key.

### 1. `storefront`: Larkspur Goods returns assistant (13 tasks)

An online shop's returns assistant (`returns-agent`, tools `lookup_order` and `issue_refund`) with 60 days of history (1 June – 30 July 2026) across three releases (`1.3.0`, `1.4.0`, `1.4.1`).

The world builds in two variants from independent random streams (so adding diagnosis incidents never shifts the base tasks):
- **Base history** (`2,997` sessions, used by `C1`–`C7`): standing faults across all 60 days—euro card confirmations quoting 100× the refund (`182` base / `195` diag), > 3 order lookups (`131` / `135`), idle timeouts where the customer simply left (`143` / `144` — *not* a bug), curt replies ending normally without a closing courtesy (`19`), late refunds > 30 days after delivery (`27` / `30`), and double refunds (`17`).
- **Diagnosis history** (`3,117` sessions, used by `C1h` and `D6`–`D9`): adds four dated incidents—shipping over-refunds (`15–28 Jun`, `49` total over-refunds in D6's key including double refunds), an order-service retry outage (`21 Jun`, `32`), a `summer-sale` traffic surge (`4 Jul`, `+120`), and a silent provider swap to `gpt-5.4-mini-2026-07-08` (`9–18 Jul`, `355`, ~2.2× slower).

The store also starts with a 40-session human-reviewed cohort (`reviewed-july`), `checks.txt`, and pre-registered evaluators including `polite-closing` (which wrongly fails idle timeouts) and `refund-issued-once` (v1 & v2).

![storefront timeline of releases and planted events](charts/kb-storefront.svg)

#### Checks (`C1`–`C7`, 8 tasks)

| task | goal | the trap & how it's graded |
|---|---|---|
| `c1-rule-from-builtins` | *(base)* Score every session from 24 July onward on *"at most 3 order lookups"* using a built-in evaluator. | **Trap:** That week has 359 sessions vs Kitaru's 100-per-request limit; the obvious built-in only describes and leaves `passed` empty; "more than 3" is easy to miscode as `≤ 2`; evaluating older sessions fails.<br>**Graded on:** Exact verdicts on all 359 sessions, ≤ 50 older sessions evaluated. |
| `c1h-two-rules-from-builtins` | *(diag)* As C1 for 9–15 July, plus *"every model call served by exact `gpt-5.4-mini`"*, one distinct built-in per rule. | **Trap:** The obvious model-match built-in treats the dated snapshot as a hold rather than a failure, leaving the 210 swapped sessions without a verdict.<br>**Graded on:** Both rules right on all 345 sessions. |
| `c2-finding-to-check` | *(base)* Write and register an evaluator that fails sessions whose reply quotes 100× the refund. | **Trap:** Overfitting to *"euro + card + after 1.3.0"* fails hidden tests that add store credit, release `1.5.0`, yen, and valid partial refunds where the order total equals 100× the refund.<br>**Graded on:** Latest version run by grader on 120 unseen sessions (precision & recall ≥ 0.9). |
| `c3-evaluator-is-wrong` | *(base)* `polite-closing` fails 1 in 20 sessions: diagnose whether assistant or check is wrong and register a fixed version. | **Trap:** Most failures are harmless idle timeouts, but naive rules (*"pass questions"*, *"pass long replies"*, *"only check refunds"*) misclassify real curt replies.<br>**Graded on:** Version ≥ 2 on 120 unseen sessions (precision & recall ≥ 0.9). |
| `c4-backfill-one-release` | *(base)* Backfill every session of release `1.4.1` with `refund-issued-once@2`, nothing earlier. | **Trap:** 464 sessions against the 100/request batch limit, with tight caps (≤ 30 older sessions, ≤ 1,400 total results).<br>**Graded on:** Stored verdicts on all 464 sessions within caps. |
| `c5-agree-with-reviewers` | *(base)* Write an evaluator matching the 40 human reviews in `reviewed-july` and generalizing to unreviewed chats. | **Trap:** Must infer *two* rules from reviewer notes (refund > 30 days after delivery, and wrong amount in reply); day 30 is allowed, and the hidden set is packed with day-30 edge cases.<br>**Graded on:** Precision & recall ≥ 0.9 on 120 unseen sessions, plus ≥ 0.9 agreement on the 40 reviews. |
| `c6-check-before-merge` | *(base)* Write `bin/check.sh <cohort>` to run release checks on every member: exit `0` if ≥ 90% pass, `1` if below, `2` on error. | **Trap:** Hidden cohorts have 130 members (> 100 batch limit) and sit right across the threshold (`92.3%` vs `87.7%`); computing locally without storing verdicts in Kitaru fails.<br>**Graded on:** Exit codes and stored verdicts across 4 randomly named hidden cohorts. |
| `c7-fix-check-then-backfill` | *(base)* C3 and C4 combined: fix `polite-closing`, then backfill release `1.4.1` under result caps. | **Trap:** Exploring by running the broken evaluator across whole releases blows the result cap.<br>**Graded on:** Stored backfill results within caps, plus C3's 120 unseen sessions. |

#### Diagnosis (`D6`–`D9`, 5 tasks — all on diagnosis history)

| task | goal | the trap & how it's graded |
|---|---|---|
| `d6-refunded-too-much` | Build a cohort of every session where total refunded exceeds the order cost. | **Trap:** The louder euro-reply bug is a decoy (its actual refunds were right); using `>=` catches normal full refunds; checking per-call misses double refunds.<br>**Graded on:** Cohort precision & recall ≥ 0.9 against the 49 sessions. |
| `d7-slower-no-release` | Build a cohort of slower sessions, plus the cause and first affected day. | **Trap:** Cause is visible only by comparing `model` vs `requested_model`; days 1–4 hit only ~35% of traffic, so selecting *"whole window"* or *"100%-slow days only"* both fail.<br>**Graded on:** Cohort vs 355 sessions, `cause: served_model_changed`, day `2026-07-09`. |
| `d8-six-to-read` | Open an investigation linking 3–6 sessions from the last week that a human should read (`problematic`, ≥ 2 fault types). | **Trap:** Most `polite-closing` failures are harmless idle timeouts, not real bugs.<br>**Graded on:** Every linked session must be a genuine planted fault with ≥ 2 distinct kinds. |
| `d8h-triage-check-failures` | Link *every* session from the last week failed by either check, assigning `acceptable` or `problematic` to each. | **Trap:** Idle timeouts are `acceptable` while curt replies and double refunds are `problematic`; assuming *"ends in a question = waiting on customer"* mislabels curt replies.<br>**Graded on:** Exact set of links and exact verdicts. |
| `d9-retries-or-traffic` | Cost spiked on two days: produce one cohort and one cause per day. | **Trap:** Spike 1 (`21 Jun`) is retry loops; Spike 2 (`4 Jul`) is ordinary-cost promo traffic—filtering for *"most expensive sessions"* finds Spike 1 and misses Spike 2.<br>**Graded on:** Cohorts vs 32 & 120 sessions, dates, causes `retry_loop` and `traffic_increase`. |

---

### 2. `clinic`: Fernhill Vets appointment assistant (5 tasks)

A veterinary chain's booking assistant (`booking-agent`, 10 tools, 10 clinics across 3 towns) with `3,211` conversations from 1 June to 20 July 2026, three releases (`1.1.0`, `1.2.0`, `1.3.0`), and a git repository with five dated commits matching the timeline.

The theme of `clinic` is **confounding changes**: releases, prompt edits, config commits, partner traffic, and backend quirks all overlap so naive *"what shipped that week?"* reasoning picks the decoy.

![clinic timeline of releases, commits, and planted events](charts/kb-clinic.svg)

How the story unfolds:
1. **15 Jun:** The scheduling API starts booking Harbour Street into Harbour Square and Mill Road into Millbrook Road (~7 in 10 times), while the assistant's reply still echoes the clinic the customer asked for. Search also returns the wrong clinic first, causing a visible double search. From **17 Jun**, 13 customers write back to complain in *separate* sessions.
2. **21–25 Jun:** Release `1.2.0` ("shorter greeting") rolls out gradually (`20% → 100%`) at the exact same cost as `1.1.0`—a pure decoy for the cost jump starting **22 Jun**, when a partner portal begins sending ~7 new patients/day (3× as many model calls, raising average cost from `$0.000809` to `$0.001108`).
3. **27 Jun:** After a **26 Jun** prompt commit for a litter check-up offer, owners try to book 4–7 pets at once and hit an existing 3-pet booking limit (`422` refusal). Tool-failure rate jumps from `1.7%` to `5.5%`, yet **nothing is broken**.
4. **1 Jul 08:05:** Commit 3 cuts `max_tokens` from `400` to `120` in `config.yaml` with **no release**—cutting off 288 longer replies (`finish_reason: length`).
5. **9 Jul:** Release `1.3.0` asks search for exact matches first. The double search disappears, making the hotfix *look* successful—yet 98 more wrong-clinic bookings still happen under `1.3.0`.

| task | goal | the trap & how it's graded |
|---|---|---|
| `d1-wrong-clinic` | Build a cohort of every booking made at a different clinic than requested. | **Trap:** Reply text names the *requested* clinic, so text search finds nothing (truth is in `book_appointment`'s tool result); the 13 complaint chats are a decoy.<br>**Graded on:** Cohort precision & recall ≥ 0.9 against 269 sessions. |
| `d2-was-it-the-release` | Build a cohort of the sessions driving the late-June cost rise and name the cause. | **Trap:** Release `1.2.0` rolled out on the exact same days, yet costs the same as `1.1.0`.<br>**Graded on:** Cohort vs 207 partner sessions, `cause: traffic_mix_changed`. |
| `d3-answers-cut-off` | Build a cohort of cut-off replies, plus the responsible git commit and first day. | **Trap:** No release went out; newest commit (`1.3.0`) is a decoy; reverting the config violates *"do not edit the repo"*.<br>**Graded on:** Cohort vs 288 sessions, commit 3 SHA, day `2026-07-01`. |
| `d4-what-broke` | Build a cohort of the tool failures behind the late-June jump and name the cause. | **Trap:** Nothing broke—customers began requesting 4–7 pets against an old 3-pet limit; blaming an outage or the 26 Jun prompt commit fails.<br>**Graded on:** Cohort vs 67 sessions, `cause: expected_rejection`. |
| `d5-did-the-hotfix-work` | Build a cohort of wrong-clinic bookings still happening under `1.3.0` (empty is legal). | **Trap:** `1.3.0` eliminated the visible double-search symptom, making *"it worked, leave cohort empty"* tempting and wrong.<br>**Graded on:** Cohort vs 98 sessions. |

---

### 3. `exports`: Tidewater Couriers (7 tasks)

A courier company starting with **no recorded Kitaru history** and two assistants traced elsewhere:
- **`dispatch-agent`** writes an in-house JSONL log (`docs/trace-format.md`) with real-world messiness: interleaved sessions, truncated lines, missing `end` records, nested tool calls (`plan_route` → `geocode`), and cost in millionths of a dollar.
- **`support-assistant`** was traced in Langfuse (1–4 turns per ticket, 1 trace per turn). Langfuse's `sessionId` tracks the chat-widget visit rather than the support ticket—30% of tickets share a visit, and tickets continue across visits (`metadata.ticket.id` holds the true ticket ID):

![I2: Langfuse sessionId vs metadata.ticket.id](charts/kb-exports-langfuse.svg)

For the nightly-import tasks (`I4`, `I4h`), each night's export covers the last two days so Kitaru deduplicates overlapping tickets by source identity. On 5 August, a commit changed the source identity from `tidewater-support` to the filename—breaking deduplication on nights 6 and 7:

![I4 and I4h: 2-day sliding window creating strays and stray-only tickets](charts/kb-exports-nightly.svg)

| task | goal | the trap & how it's graded |
|---|---|---|
| `i1-import-an-export` | Import a 90-ticket Langfuse export for a new agent with two releases under the right source identity. | **Trap:** Omitting source identity fails every ticket while the CLI still exits clean; release is per-trace and ~12% of tickets cross releases.<br>**Graded on:** Stored Kitaru sessions vs export (tickets, versions, call counts, cost). |
| `i2-one-ticket-one-session` | Write a script importing a Langfuse export as one session per whole ticket, dropping monitoring probes. | **Trap:** Default import groups by `sessionId` (widget visit), mixing and splitting tickets.<br>**Graded on:** Given export, then script run on a hidden export. |
| `i3-write-an-importer` | Write and register custom importer `tw-trace` for `dispatch-agent`'s JSONL format. | **Trap:** Interleaving, truncated lines, missing `end` (session must be `failed`), nested tool calls, missing `cached` key, micro-dollar cost units.<br>**Graded on:** Latest importer run on a 150-session hidden log, compared node by node. |
| `i3h-messy-log` | As I3, on a messier log format. | **Trap:** Batch calls omit cost (must compute from price table), ~3% duplicate lines, model calls nested under tools, and hidden log uses ISO timestamps with UTC offsets absent from the sample.<br>**Graded on:** Hidden log compared node by node, as I3. |
| `i4-nightly-import-twice` | Fix `bin/nightly_import.sh` and repair the damaged store so every ticket exists once while preserving existing good sessions and `reviewed-week-31`. | **Trap:** Wiping & re-importing destroys the reviewed cohort's session IDs; simply deleting all 96 strays loses the 48 tickets of days 6–7 that exist *only* as strays.<br>**Graded on:** Store vs files and snapshot, then script run twice on night 8 (2nd run = 0 new sessions). |
| `i4h-strays-at-scale` | As I4, plus `bin/remove_strays.sh` for larger stores. | **Trap:** Grader tests on ~1,900 sessions—more than a single API/CLI page, breaking unpaginated scripts.<br>**Graded on:** I4 checks, then script run on 500 strays + 1,200 good sessions. |
| `i5-invoice-does-not-match` | August cost in Kitaru is a third below the provider's bill: fix the importer and correct August's sessions. | **Trap:** Two bugs—model calls under tools are dropped (`31.7%` of cost) and cached tokens are ignored; re-importing without deleting skips existing IDs.<br>**Graded on:** August's 450 sessions vs log, plus hidden log; importer v1 must stay intact. |

---

### 4. `helpdesk-live`: a runnable helpdesk agent (4 tasks)

A real PydanticAI `helpdesk-agent` backed by a deterministic Python `planner.py` (so replaying a request is reproducible). Four tools read local JSON files; `issue_refund` and `escalate_to_human` hit the **finance service** (`:8091`), which appends every call to a root-only file.

- **History:** `260` recorded requests—`REQ-0001..0200` on release `1.6.0`, `REQ-0201..0260` on `1.6.1` (`58` refunds including `19` in euros, `36` escalations). Cohort `refunds-to-recheck` holds `32` non-euro refunds from `1.6.0`.
- **Planted bug:** `money.to_major` divides USD and GBP by 100 but passes EUR through (100× too large). JPY is already right because yen has no minor unit.

| task | goal | the trap & how it's graded |
|---|---|---|
| `f1-replay-without-refunding` | Replay the 32-session `refunds-to-recheck` cohort against version 2 without paying anyone again. | **Trap:** Default replay tool policy is `live`, which pays all 32 customers a second time.<br>**Graded on:** Completed replays reaching `issue_refund` per member; finance ledger row count unchanged. |
| `f2-fix-euro-with-evidence` | Fix the currency bug in release `1.6.2` and prove it via an experiment that pays nobody *(walked through above)*. | **Trap:** All-recorded fails on changed refund args; live pays everyone; *"divide all by 100"* breaks yen.<br>**Graded on:** Prior releases untouched, experiment evidence, finance unchanged, 24 unseen 4-currency requests replayed. |
| `f3-refunds-far-too-large` | Symptom only (*"some refunds are far too large"*): diagnose, fix, and release without paying anyone. | **Trap:** Testing the live agent manually hits the finance service; naive `/ 100` breaks yen.<br>**Graded on:** As F2, without requiring an experiment. |
| `f4-experiment-keeps-failing` | An existing experiment for the fixed release fails every run: get a completed run over all 58 refunds without running `issue_refund` live. | **Trap:** The 19 fixed euro calls have new args absent from recordings; `passthrough` pays them; an experiment with prior runs returns `409` on policy edits, so a new experiment is needed.<br>**Graded on:** Completed run across all 58, no live refund calls, finance unchanged. |

---

### 5. `helpdesk-services`: live services, performance & setup (8 tasks)

The same container image hosts **two distinct groups of tasks**: four replay/optimization tasks (`F5`–`F8`) on `helpdesk-agent` v2.0.0, and four operational setup tasks (`O1`–`O4`) that reuse the container's Kitaru stack and services for worker, PydanticAI, and LangGraph exercises.

#### Replay & optimization (`F5`–`F8`, 4 tasks)

In release `2.0.0`, `helpdesk-agent` reads orders from a deliberately constrained **order service** (`:8092`: `0.25 s` per call, max 4 concurrent requests before returning HTTP `429`, root-only request log) alongside the same finance service (`:8091`).

![helpdesk-services topology and F6 concurrency trap](charts/kb-helpdesk-services.svg)

- **History:** `420` recorded requests on `2.0.0` (`225` refunds, `114` status checks, `81` disputes; `98` refunds paid, `81` escalations). `F8` uses a variant history with `67` single-item refund requests where `2.0.0` wrongly refunds the whole order.
- **Planted inefficiencies (`F5`):** Seven places where `planner.py` asks a service the same thing twice:
  - *Never changes (remove these 3):* re-reading a multi-item order on status checks; re-reading customer before escalation; re-checking policy before refusal.
  - *Always changes (keep these 2):* retry after timeout; second check on `label_created` parcels.
  - *Rarely changes (keep these 2!):* re-read before paying (`credit_lands`: only **6** cases in 420); out-for-delivery check (`arrives_now`: only **4** cases in 420).
- **Low-effort behavior (`F7`):** At `reasoning_effort: low`, `96` of the `420` sessions end differently—the `81` disputes *plus* `15` non-dispute sessions that only surface by replaying all 420 against their recordings.

| task | goal | the trap & how it's graded |
|---|---|---|
| `f5-stop-asking-twice` | Remove the second asks that never returned new data across the 420 runs, keeping the ones that did. | **Trap:** Two of the 7 repeats differ in only 6 and 4 sessions—inspecting a small sample deletes them; manual live testing triggers refunds.<br>**Graded on:** Hidden requests through `2.0.0` vs new version: identical answers & payments, lookups reduced by *exactly* the 3 wasteful repeats. |
| `f6-run-them-together` | Run independent lookups concurrently without altering calls or answers. | **Trap:** Recorded chats mention ≤ 2 orders, while hidden chats ask about up to 6—unbounded concurrency passes locally and triggers `429` errors during grading.<br>**Graded on:** Identical calls & answers, overlapping lookups, ≤ 0.75× wall time on multi-order chats, zero `429`s. |
| `f7-where-low-effort-is-safe` | Build a cohort of sessions that end identically at `reasoning_effort: low`, proved with an experiment that pays nobody. | **Trap:** Reading `planner.py` suggests *"everything except disputes"*, missing the 15 non-dispute differences.<br>**Graded on:** Cohort vs all 324 safe sessions (≥ 95%, zero unsafe included) + completed experiment with the override. |
| `f8-pick-between-two-fixes` | Evaluate Ana's and Ben's one-item refund fixes on one fair cohort and release the better one. | **Trap:** Ana's fix passes her 24 cherry-picked chats but fails when `quantity > 1` or a discount applies; Ben's fix is right, yet his existing experiment fails because it calls a new read-only tool absent from recordings.<br>**Graded on:** Fair experiment evidence + unseen requests through released version paying exact owed amounts. |

#### Setup & instrumentation (`O1`–`O4`, 4 tasks)

These tasks reuse the `helpdesk-services` container to test Kitaru worker configuration and agent instrumentation (including separate `parcel-chaser` and LangGraph agents):

| task | goal | the trap & how it's graded |
|---|---|---|
| `o1-nothing-is-running` | Fix the team's worker start script so it claims evaluations and replays (including future agent versions), but never imports. | **Trap:** Passing an explicit `--claim` replaces Kitaru's defaults rather than adding to them, silently dropping other job types.<br>**Graded on:** Grader launches the worker with the script and verifies claimed jobs (plus an import left pending) within 5 minutes. |
| `o2-record-this-agent` | Record an unrecorded PydanticAI agent (`parcel-chaser`) in Kitaru and register a replayable version. | **Trap:** The agent is constructed in two places and launched two ways (wrapping only one leaves the other unrecorded); registered command must accept the worker's order argument.<br>**Graded on:** Both entrypoints on hidden orders, then replays answered entirely from recordings (0 order-service calls). |
| `o3-make-it-replayable` | Make existing recorded runs replayable without modifying the planner or tools. | **Trap:** Four layered causes revealed one at a time: missing replay capabilities, another host's working directory, an entrypoint expecting an argument, and an env var set only in the shell wrapper.<br>**Graded on:** Hidden & recorded sessions replayed with a low-effort override; all complete; nobody paid. |
| `o4-record-a-langgraph-agent` | Record an unrecorded LangGraph agent with Kitaru's LangGraph adapter so it is replayable. | **Trap:** Wrapping the compiled graph records runs but cannot replay tools from recordings; only the adapter's factory path supports replay, and it rejects `stream()` so reading code must adapt while keeping output identical.<br>**Graded on:** As O2, across the agent's entrypoint. |

---

## How a run works & why the scores are trustworthy

Every task runs in a single container holding PostgreSQL, the Kitaru server, a worker, the company repo, and the coding agent.

![How one Kitaru Bench attempt runs](charts/kb-how-a-run-works.svg)

### Isolation & grading guarantees

- **Three Linux users:** Harbor's healthcheck runs `/opt/kitaru-bench/start.sh` as `root` (picking a fresh Postgres password each attempt) and starts `bench-worker`. The agent runs as unprivileged user `agent`, reaching Kitaru only over HTTP (`http://127.0.0.1:8000`)—it cannot inspect PostgreSQL, `/tests`, or the root-only finance/order logs.
- **Safe execution of agent-written code:** When grading an agent's evaluator or importer, `start_grader_worker()` locks `/tests`, `/solution`, and `/logs` to `root`, kills every agent process, and runs the registered code under a third user, `grader`. Every such task includes a `read_grader_labels.sh` shortcut that attempts to read the answer key and **must score 0**.
- **Network & runtime:** Egress is restricted to `api.anthropic.com`, `api.openai.com`, and `chatgpt.com` (no PyPI; plugin wheels and `/opt/kitaru-docs` are baked in). Because Harbor's local Docker runner rejects allow-lists, Kitaru tasks run on Modal (`--env modal`), while Prime's runner uses prebuilt per-task images from `kitaru/scripts/build_on_modal.py`. Agent timeout is 30 minutes (45 minutes on `f7`) with 2 CPUs.
- **Four checks before a task counts:** Reference solution passes `5/5`, doing nothing scores `0`, every shortcut in `tests/shortcuts/` scores `0`, and a second, different valid solution scores `1`.

### What the grader reads (no prose parsing)

| artifact | what the agent leaves | what the grader verifies |
|---|---|---|
| **cohort** | a named set of sessions | precision & recall ≥ `0.9` against ground truth (latest cohort version counts) |
| **investigation** | linked sessions + verdicts (`problematic` / `acceptable`) | exact link set and verdicts |
| **evaluation results** | per-session verdicts from an evaluator | coverage, accuracy, and caps on total/older sessions evaluated |
| **registered code** | an evaluator, importer, or agent version | executed by the `grader` worker against hidden sessions, logs, or requests |
| **`answer.json`** | cause category, commit SHA, or date | exact match alongside the cohort |
| **service logs** | rows written by finance (`:8091`) & order (`:8092`) services | row counts before & after; one extra refund row scores `0` |

## Where things live

| what | where |
|---|---|
| Base image (Postgres, Kitaru, agent CLIs, wheels, docs) | `kitaru/base/` (`zenmldocker/kitaru-bench-base`, digest pinned in `kitaru/base/IMAGE`) |
| World definitions (5 total) | `kitaru/worlds/<world>/` (`story.py`, `load.py`, `Dockerfile.world`, `workspace/`) |
| Task definitions (37 total) | `kitaru/tasks/<id>/` (`instruction.md`, `task.toml`, `world`, optional `plants`, `setup/`, `workspace/`, `solution/`, `tests/`) |
| Generated image recipe & answer key | `kitaru/tasks/<id>/environment/` and `tests/fixtures/ground_truth.json` (generated by `kitaru/scripts/sync_env.sh`; do not edit by hand) |
| Grader helpers | `kitaru/checks/kitaru_checks.py` (copied into each task's `tests/`) |
| Design decisions & transcript notes | [`docs/decisions.md`](decisions.md) (from 2026-11-20), `results/kitaru-level1.md` – `kitaru-level3.md` |
