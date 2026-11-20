# Kitaru tasks for zenml-bench — proposal

Status: draft for Alex, 20 November 2026. Nothing here is built. Read `docs/2026-09-09-plan.md` first if the ZenML benchmark's rules are not fresh; this document only says what changes for Kitaru.

Sources read: this repo (brief, `task-authoring.md`, `findings.md`, `publishing.md`, `decisions.md`), `kaizen/benchmarks/` (fixtures, 17 Kitaru tasks, the `building-harbor-benchmarks` skill, `results/`), and Kitaru at `0.27.7+dev` (commit `38bfb11`: CLI registry, `openapi/openapi.json`, worker, PydanticAI adapter, `docs/book/`). Anything marked **(spike)** was read from code but not run, and must be run before a task depends on it.

## 1. Summary

Thirty-two hand-built tasks in five families, on four reusable example companies ("worlds"), in the same Harbor format and under the same four verifier checks as the ZenML set. The families follow the four steps Kitaru's own product page uses, plus one for running Kitaru itself:

| family | product step | tasks | what the agent does | how it is graded |
|---|---|---|---|---|
| I — import | bring your traces | 5 | gets trace exports into Kitaru correctly, writes or repairs an importer | the grader imports a file the agent never saw through the agent's registered importer and compares the sessions Kitaru stored |
| D — diagnose | get insights | 9 | finds what went wrong across thousands of sessions | the agent records its answer *in Kitaru* as a cohort; the grader scores the cohort's membership against the planted sessions |
| C — checks | turn findings into checks | 6 | writes, repairs and runs evaluators | the grader runs the agent's registered evaluator on labeled sessions the agent never saw |
| F — fix and replay | replay a fix before it ships | 8 | fixes the example agent and proves the fix with replays and experiments | the grader replays hidden sessions against the agent's fixed version, and checks that no replay repeated a real-world side effect |
| O — operate | (running Kitaru) | 4 | repairs a worker that claims the wrong jobs, instruments an unrecorded agent | the grader submits its own jobs or runs the entrypoint itself and reads what Kitaru recorded |

Three things are different from the ZenML set and drive most of the design:

1. **Kitaru has no local-file mode.** ZenML's client writes to a SQLite file with no server, so a ZenML task is one Python process. Kitaru is a FastAPI server on PostgreSQL plus separate worker processes (`_DRIVER = "postgresql+asyncpg"` is hard-coded in `server/database/service.py`; there is no SQLite path anywhere in `src/kitaru`). Every Kitaru task container therefore has to run Postgres, the server and usually a worker before the agent starts. Section 4.
2. **Replay calls the model again.** When Kitaru replays a session, a worker starts the agent's own program, the adapter serves *tool* results from the recording, and the *model* is called live (`wrap_model_request` in the PydanticAI adapter ends in `await handler(effective)`). A benchmark cannot depend on a live model inside the thing being graded, so the example agents use a scripted stand-in for the model. Section 5.
3. **The diagnosis tasks already exist privately, and they saturate.** `kaizen/benchmarks` has 17 Kitaru tasks. Its own results say that once an agent is told a Kitaru workspace exists, five of six rail tasks pass on every setup, and the optimization tasks are "too easy to separate setups". The public set should reuse the *method* (how the fake history is built, the trap table, the grader lessons), write new stories, and raise the bar from "point at one affected session" to "build the complete set". Sections 3 and 6.

## 2. What we would be measuring

The ZenML set asks "can a coding agent use ZenML?". The Kitaru set asks the same about Kitaru, one family per product step. The value is the same three things as before: a regression suite for Kitaru's agent-facing aids (the `zenml-io/kitaru-skills` repo, the `kitaru-mcp` server, the docs), a list of where agents trip that turns into docs and CLI fixes, and a public leaderboard.

One positioning question is Alex's to settle before publishing, not before building: family D measures the job the paid hosted AI engineer does (read the traces, find the problem). Kaizen's internal numbers were 17/18 for the product agent against 15/18 for a bare agent that had been given one paragraph saying the workspace exists. A public leaderboard on that family will show generic agents doing well. The cohort-based grading in section 6 makes the family harder than kaizen's version, but the question of whether that row belongs on a public page is a marketing call.

## 3. What to take from `kaizen/benchmarks`, and what to leave

**Take the method.** These are tested and written down in `kaizen/benchmarks/.agents/skills/building-harbor-benchmarks/references/`:

- *How a fake history is built.* One `story.py` produces every session as plain data from a fixed seed: no model is called, no agent runs. `generate.py` posts them to a running Kitaru server over REST (`POST /api/v1/sessions` with `origin: "imported"`, then `POST /sessions/{id}/nodes`) while the Docker image is being built. The answer key is derived from the same story, and the build fails if the server's totals disagree with it. Loading 8,000 sessions takes about 75 seconds.
- *Every planted problem gets a trap.* A decoy that looks like the cause (a version rollout on the same days as the real traffic change), a case where nothing is broken (group bookings correctly rejected with 422), a metric that improved because the agent got worse (fewer escalations because it stopped checking invoices). The trap table in `fixture-design.md` lists ten patterns.
- *Platform quirks already found.* Session numbers follow creation order, not `started_at`, so sessions must be created one at a time in start order. The CLI and MCP mask any key ending in `tokens` (so `max_tokens` shows as `***`) while raw REST does not. Server-side filters cannot use metadata, model or session number. A finished session accepts nodes only if it is imported.
- *Grader lessons.* Most surprises were graders rejecting correct answers: a count of passengers where the key had tickets, `Session numbers 961, 967` that the parser could not read, a correct extra citation that zeroed the score. Kaizen's fix was a closed list of cause labels and tolerances on counts.

**Leave the stories.** Three reasons:

1. If the same six companies are public, they end up in training data, and kaizen's internal comparison of the product agent against bare agents stops meaning anything. Keeping kaizen's fixtures private gives us the private held-out set the ZenML brief asked for (decision 8) at no cost.
2. They carry the internal codename in task ids, image tags and container paths, plus teammate names, a Modal workspace name and OpenAI rate limits in the results files.
3. `kitaru_support` was written from the same internal use-case draft as the `kitaru-playbook` skill, so that skill cannot be tested fairly on it.

**Leave three design choices** that fit kaizen's question and not ours:

- *Time shifting.* Kaizen moves every timestamp at container start so "the newest session ended 45 minutes ago". It cost them a round of results (records landed weeks in the future; one run just after midnight scored 0). We freeze the calendar instead: the instruction says "this is a snapshot taken on 30 July 2026" and asks about day ranges, never "yesterday". Nothing has to run at container start for time to be right.
- *Free-text answers.* Kaizen grades `answer.json` with a list of free-text `points_to` entries that a resolver turns into session ids. We have the agent record its answer in Kitaru (section 6), which removes the parser.
- *No worker.* Kaizen's server sidecar runs no worker, so nothing that needs one (imports, evaluator runs, replays, experiments) can be a task. Four of our five families need a worker.

`claims-over-time` is not reusable from here: only the product-agent adapter for it lives in kaizen. The benchmark itself is in `zenml-io/agent-benchmarks`, which this session could not read. Worth a look before starting, both for overlap and because a public "agent benchmarks" repository already exists (section 8).

## 4. The container: where Kitaru runs

A Kitaru task needs three long-running processes that a ZenML task does not: PostgreSQL, the Kitaru server (`uvicorn kitaru.server.api.main:app --factory`), and for most tasks a worker (`kitaru worker start`). `kitaru login --local` is not an option inside a task container, because it starts those through Docker or Podman. Kitaru's own CI shows the route without Docker: `examples/python/pydantic_ai_ticket_resolver/scripts/run_ci_e2e.py` starts `uvicorn` with `KITARU_SERVER_AUTH_SCHEME=none`, the `KITARU_SERVER_DB_*` variables and two required keys, and the server creates the database and runs its migrations itself.

The choice is where those processes live. Three concrete arrangements:

- **Arrangement A — everything in the agent's container.** One image holds Postgres, the server, the worker, the agent CLIs and the project. Something starts the three processes when the container starts. *What works:* runs on every sandbox provider and through the Prime wrapper, which the ZenML brief made a requirement (decision 10) because verifiers did not support sidecars. *What breaks:* the Postgres data directory is on the agent's disk. An agent can run `psql` and write an evaluation row or a replay row by hand, exactly as agents could edit ZenML's SQLite file. And both Harbor and verifiers replace the image's entrypoint with a keep-alive, so "something starts the processes" needs a mechanism we have not found yet **(spike)**.
- **Arrangement B — Kitaru in a second container.** The task ships a `docker-compose.yaml` that adds a `kitaru` container (Postgres + server + worker) next to the agent's. This is what kaizen does, with a health check so the agent starts only when the server answers. *What works:* the agent can reach Kitaru only over HTTP, so it cannot touch the database; startup is ordinary compose. *What breaks:* compose sidecars run on Docker, Podman and Modal but not through the verifiers wrapper as of September **(verify; two months old)**, so the set could go on the Harbor Hub but not the Prime Environments Hub. The worker also sits in the other container, which means the agent cannot fix a broken worker (family O) or edit the example agent that the worker launches for replays (family F) unless the project directory is shared between the two.
- **Arrangement C — one container, two Unix users.** As A, but Postgres and the server run as user `kitaru` with a data directory the agent's user cannot read, and the agent gets no database password. The agent reaches Kitaru over `localhost:8000` only. *What works:* single container, so Prime-compatible; database tampering closed off. *What breaks:* depends on the agent not running as root, which Harbor and each sandbox runtime decide **(spike; the ZenML brief flagged the same question and never needed the answer)**.

Recommendation: **build for A, harden toward C if the user-switching spike passes, and keep graders honest by re-running things themselves** (section 6), the same stance the ZenML set took on its forgeable SQLite file. Reason: publishing to both Hubs is the stated goal, and families F and O need the worker and the agent's code in the same place.

Other facts that shape the base image:

- **Built-in plugins are downloaded when a job runs.** The server stores only a requirement string such as `kitaru-evaluator==0.3.0`. When a worker claims an evaluation job it runs `uv run --no-project --with kitaru-evaluator==0.3.0 python -m kitaru.task ...` (`worker/process.py`, `get_python_run_argv`). In a container with the network off that download fails. Kitaru's CI solves it with a directory of wheels and two variables, `UV_FIND_LINKS=<dir>` and `UV_NO_INDEX=1` (`.github/workflows/ci.yml`). The base image bakes that directory in **(spike)**. A script plugin with no dependencies runs with the worker's own Python and needs neither.
- **Auth.** `KITARU_SERVER_AUTH_SCHEME=none` makes every request the default admin account. That is the simplest setting and what kaizen uses. Accounts have an `is_admin` flag, so a tighter setup (agent gets a non-admin key, grader keeps the admin one) is possible; whether it closes anything useful is part of the tamper inventory **(spike)**.
- **A fresh store in about a second.** `grade_local.sh` gives every ZenML grading run a new SQLite file. The Kitaru equivalent is PostgreSQL's template copy: load a world once into database `world_rail`, then `CREATE DATABASE trial_123 TEMPLATE world_rail` for each run. Kitaru's own `devtools/stack.py db snapshot|restore` does this.
- **Pins.** Kitaru `0.27.7` (latest changelog entry, 10 November; confirm on PyPI), Python 3.13 (what Kitaru's release images use; 3.14 is supported). The grader needs only `pip install kitaru`: the client's base dependencies are `pydantic` and `httpx`. Harbor: this repo pins 0.22.0, kaizen runs 0.23.0; decide once for the whole repo.
- **Docs in the box.** `docs/book/` at the pinned tag is plain Markdown and is the offline documentation snapshot. `kitaru schema` prints the whole command tree offline, and `kitaru_docs_search` in the MCP server uses an index shipped in the wheel.

## 5. The model inside the example agents

Family F needs an agent that Kitaru can actually re-run. Kitaru's quickstart agent hard-codes `openai:gpt-5-nano`, and its own end-to-end test stops before the replay step for that reason.

What replay does, step by step: the grader (or the agent under test) asks for a replay of session 412. A worker starts the example agent's program with session 412's original input. The agent asks its model what to do. The model says "call `lookup_order`". The Kitaru adapter intercepts that tool call and, depending on the *tool policy*, either runs the real tool (`passthrough`, the default), returns the result recorded in session 412 (`history`), or returns a fixed value (`static`). The run is stored as a new session with `origin: replay`, and evaluators run on it.

Three ways to give that agent a model:

- **Scripted model (recommended).** The example agents are real PydanticAI agents recorded through the real `kitaru-pydantic-ai` adapter, but the model object is PydanticAI's `FunctionModel`: a Python function that reads the conversation and returns the next message. Kitaru's adapter tests already do this. *What works:* replays give the same result every time, cost nothing, need no network. *What breaks:* faults have to live in code the scripted model exercises (tools, formatters, configuration, retry logic), not in prompt wording, because a scripted model does not really read a prompt. The function is in the image; the grader uses its own copy, the way the research tasks keep a private copy of `prepare.py`.
- **A small live model through the allowlist.** The example agent calls a cheap hosted model. *What works:* prompt regressions become real tasks. *What breaks:* the oracle no longer passes 5/5 by construction, every trial costs money on top of the agent under test, and results drift when the provider changes the model. Not for the core set; possibly a later track.
- **No runnable agent.** Family F becomes "define the experiment correctly" with nothing executed. *What breaks:* the grader can only check configuration, and the most distinctive thing Kitaru does is untested.

Everything except the model is real Kitaru at a pinned version: real server, real worker, real adapter, real importer and evaluator plugins. That is the Kitaru form of the ZenML brief's "nothing about ZenML is mocked".

## 6. How Kitaru tasks are graded

The ZenML rules carry over unchanged: grade what the product recorded, never the agent's source text; hidden inputs; four checks per task (reference passes 5/5, doing nothing scores 0, each named shortcut scores 0, a different valid solution passes). What changes is what "recorded state" is and how the grader reads it.

**Reading state.** The grader is a Python script that talks to the Kitaru server over REST with `KitaruAPIClient` (32 resource groups: `sessions`, `evaluations`, `cohorts`, `cohort_versions`, `replays`, `experiment_runs`, `imports`, `jobs`, `tasks`, …). `shared/checks/store_integrity.py` gets a sibling, `kitaru_checks.py`.

**Fields the server sets, which an agent cannot fake through the API.** These are the Kitaru counterpart of "a cached step must point at a real original":

| claim | field that proves it | what a hand-made row looks like |
|---|---|---|
| this evaluation came from an evaluator run | `evaluator_version_id` and `task_id` set | `sessions.create_evaluations` (a manual label) leaves both empty |
| this session came from an import job | `import_id` and `task_id`, set from the worker's task token | `origin` alone is supplied by the caller and proves nothing |
| this insight came from an analyzer run | `analyzer_version_id` set | `kitaru insight create` leaves it empty |
| this replay ran | `job_id`, `result_session_id`, and a task with a `worker_id` | |

With database access (arrangement A) all of these can still be written by hand with `psql`, so they are a filter for honest mistakes, not a defense. The defense is the next rule.

**The grader re-runs the agent's work on inputs the agent never saw.** One pattern per family:

- *Import.* The agent registers an importer (or repairs one). The grader uploads its own hidden export file through that registered importer version and compares the stored sessions and nodes (tool names, token counts, parent links, cost totals) with the expected values.
- *Checks.* The agent registers an evaluator. The grader ingests its own labeled sessions (affected ones, clean ones, and near-misses built to fool a lazy rule), runs the registered evaluator version on them, and requires high precision and recall. An evaluator that always fails, or that keys on a session id it saw, fails here.
- *Fix and replay.* The agent registers a new version of the example agent. The grader replays hidden baseline sessions against that version with its own evaluator and its own tool policy.
- *Operate.* The grader starts the worker through the project's documented script and submits one job of each kind.

**The answer sheet for diagnosis tasks is a cohort.** A cohort in Kitaru is a named, versioned set of sessions. Instead of writing "sessions 961 and 967" into a file, the task says: *create a cohort named `wrong-station-tickets` containing every session in which a ticket was issued for the wrong station*. The grader reads the cohort's members (`sessions.list` filtered on `cohort_version_id`) and computes precision and recall against the planted set. This does three things at once: there is no free text to parse (kaizen's largest source of grader bugs); the agent has to use Kitaru to answer, not only read it; and "find all of them" is much harder than "find one". In kaizen's rail results the single task that separated setups was the count: the wrong answer counted the 51 complaint sessions, the right one found the 163 bookings. A cohort task is that task generalized. Where a cause has to be named, the task also asks for one field from a closed list (kaizen's eight labels), written to a small `answer.json`.

**Side effects are state too.** The example agent has a tool that changes something outside Kitaru (`issue_refund` appends to a ledger file owned by a small local service). If the agent under test replays 60 sessions with the default tool policy, the ledger gains 60 real refunds. The grader counts ledger rows. This is the AppWorld "collateral damage" check from the ZenML brief, and it makes Kitaru's most important replay setting measurable.

**Shortcuts every task ships** (`tests/shortcuts/`): `tamper_db.sh` (write the expected rows with `psql`), `manual_labels.sh` (create evaluations by hand instead of running the evaluator), plus task-specific ones named in the catalogue. Alternatives every task ships: the reference followed by ordinary agent behavior (extra exploratory imports, a throwaway cohort, a second evaluator version), because the oracle is the least realistic agent.

## 7. The four worlds

A world is one fictional company, its agent, a history of sessions and a git repository holding the agent's code, built once and reused by many tasks (the SWE-smith idea the ZenML set used for `daily_report`). Each lives under `kitaru/worlds/<name>/` with `story.py` (the single plan, seeded), `load.py` (posts it to a server at image build), `workspace/` (the agent's repo) and a derived `ground_truth.json` that goes only into `tests/`.

| world | company and agent | history | what is planted | used by |
|---|---|---|---|---|
| `clinic` | a veterinary clinic chain's appointment agent (`booking-agent`, three versions) | ~6,000 imported sessions over 50 days | a scheduling API change that resolves two clinics with similar names to the wrong one; a rollout decoy on the same days as a traffic change; a config commit with no version bump; a correct rejection that looks like an outage; a hotfix that fixed search but not booking | D1–D5, C1, C4 |
| `storefront` | an online shop's returns agent (`returns-agent`, three versions) | ~8,000 imported sessions over 60 days, a reviewed cohort of 40 sessions with verdicts, two evaluators | a prompt trim that stops an invoice check (fewer escalations, more over-refunds); a currency formatter fault; a silent served-model change (`requested_model` unchanged, `model` different); a tool that starts returning whole articles; an evaluator that fails idle-timeout sessions | D6–D9, C2, C3, C5 |
| `exports` | a company moving its tracing to Kitaru | no sessions loaded; export files in Langfuse, LangSmith and Phoenix formats plus an in-house JSONL log format, and a nightly import script | multi-turn conversations split across traces; overlapping nightly files; a custom importer that drops nested tool calls and cached tokens | I1–I5 |
| `helpdesk-live` | the returns agent again, but runnable: PydanticAI + scripted model + five tools, one with a side effect | ~300 sessions recorded by really running the agent at image build | a formatter fault that the obvious fix turns into a different fault; a repeated tool call; two independent lookups run one after the other; a cheap scripted model that is safe on routine requests and wrong on disputes | F1–F8, O1–O4 |

Why `helpdesk-live` records its sessions by running the agent instead of importing invented ones: a `history` tool policy finds the recorded result by hashing the tool name and arguments, and Kitaru's docs say the match is guaranteed only when the recording and the replay come from the same adapter. Invented sessions would miss.

Kaizen's four optimization fixtures (1,200 sessions each, generated by modular arithmetic, with the waste visible in a two-commit repo) fold into `helpdesk-live`, where each one becomes a fix that the grader measures, not a label the agent picks.

## 8. Where it lives

- **Option 1 — a `kitaru/` directory in this repo (recommended).** ZenML paths stay where they are, because the published v0.1 is frozen. `kitaru/` holds `base/Dockerfile`, `worlds/`, `checks/`, `tasks/` and its own `dataset.toml`. The root `registry.json` is already a list of datasets, so it gains a second entry, `kitaru-bench`. The Hub gets a second dataset `zenml/kitaru-bench`, task ids `zenml/kitaru-<name>`, git tags `kitaru-v0.1`. A second Prime wrapper goes in `integrations/prime/kitaru_bench/`. `verify_task.py`, `run_baselines.py`, `results_table.py`, `analyse_trajectories.py`, `check_public.sh` and `harbor_to_prime_eval.py` are reused with a suite argument. *What works:* one set of scripts, one `task-authoring.md` of rules that cost bugs to learn, one findings log. *What breaks:* the repository is called `zenml-bench` and half of it is about another product; `harbor publish` from a subdirectory needs checking **(verify)**.
- **Option 2 — a new `zenml-io/kitaru-bench` repo.** *What works:* clean name and independent versions. *What breaks:* seven scripts copied and drifting; this session cannot create repositories.
- **Option 3 — `zenml-io/agent-benchmarks`**, which already exists publicly and holds `claims-over-time`. *Unknown:* its layout and whether it is meant to grow. Read it before deciding.

## 9. Task catalogue

Ids are stable; titles are working titles. "Needs" says which processes must be running: S = Postgres and server, W = plus a worker. Each row's shortcuts are in addition to `tamper_db.sh`.

### 9.1 Import (world `exports`)

| id | title | what the agent must do | needs | acceptance | shortcuts that must fail |
|---|---|---|---|---|---|
| I1 | import an export | Import a Langfuse export for a named agent version. Traps: `--importer` and `--agent` need `NAME@VERSION`; provider importers need a source identity in `--params`; the agent must be registered first. | W | Expected sessions exist with their external ids, node counts and cost totals, under the right agent version, each with `import_id` and `task_id` set. | posting sessions directly with `origin: "imported"` |
| I2 | one conversation, one session | The export splits each multi-turn conversation across several traces. Import so that one session is one whole conversation (`--join-on`). | W | N sessions, not 3N; each holds its turns in order; a hidden second file imports the same way through the agent's script. | importing unjoined then deleting extras |
| I3 | write an importer | The in-house JSONL log format has no importer. Write and register one (`kitaru importer scaffold|test|register`). | W | The grader imports a hidden file through the registered importer version: tool names, parent links, token counts and cost match. | an importer that returns the visible file's sessions whatever the input |
| I4 | nightly import without duplicates | `bin/nightly_import.sh` created every session twice last night (it registered a second source identity) and never refreshed insights. Repair the script and the store. | W | Duplicates gone, originals kept; the grader runs the script on a hidden next-day file twice: new sessions appear once, existing ones are skipped, and analysis was rerun with `import analyze`, not by re-importing. | deleting the agent and re-importing everything (loses the reviewed cohort) |
| I5 | the invoice does not match | Symptom only: Kitaru's cost for last month is a third lower than the provider's invoice. The registered custom importer drops nested tool calls and cached-token usage. Register a corrected version and re-import. | W | Hidden file through the new importer version: totals match; the old version is still registered (versions are immutable). | patching cost totals on existing sessions |

### 9.2 Diagnose (worlds `clinic`, `storefront`)

Every task: the instruction names the workspace, the snapshot date and the cohort name to create. Pass = precision and recall each ≥ 0.9 against the planted set (thresholds tuned per task after pilots), plus the cause label where asked, plus no changes to the agent's repository.

| id | title | question | trap |
|---|---|---|---|
| D1 | wrong clinic | Customers say appointments were booked at the wrong clinic. Build the cohort of every affected booking. | Complaint sessions are a small, different set; replies repeat the customer's words, so searching reply text finds nothing. The evidence is the tool's argument against its result. |
| D2 | was it the new version? | Cost per conversation rose a third as 1.2.0 rolled out. Cohort of the sessions that explain the rise; cause label. | The rollout is a decoy; a traffic change started one day later. |
| D3 | answers cut off | Longer answers stop mid-sentence. Cohort of cut-off sessions; name the commit. | No new version was released; the cause is a config commit, and the CLI and MCP mask `max_tokens`. |
| D4 | what broke? | More conversations have a failed tool call. Cohort; cause label. | Nothing broke: the tool correctly rejects group bookings. A "fix" in the repo fails the collateral check. |
| D5 | did the hotfix work? | Did 1.3.0 fix the wrong-clinic bookings? Cohort of affected bookings made after the release (empty is a legal answer and here a wrong one). | The release fixed search, not booking. |
| D6 | was the dip real? | Escalations fell and cost fell for two weeks, then both went back. Cohort of the sessions that were handled wrongly in that window. | It looks like an improvement. |
| D7 | slower and longer | Replies got slower with no release. Cohort of sessions served by the changed model; first affected day. | `requested_model` never changed. |
| D8 | pick six to review | Open an investigation over at most six recent sessions someone should read, with a verdict on each. | Graded on the investigation Kitaru stores: at least three planted problems, none of the evaluator's false failures. |
| D9 | retries or traffic? | Cost spiked on two separate days. One cohort per day; one cause label per day. | One is a retry loop against a timing-out API, the other is a promotion email. |

### 9.3 Checks (worlds `clinic`, `storefront`)

| id | title | what the agent must do | needs | acceptance | shortcuts that must fail |
|---|---|---|---|---|---|
| C1 | a rule from the built-ins | Encode "no conversation may call `find_clinic` more than three times" with a built-in evaluator and run it over the last two weeks only. | W | Evaluations from the built-in's version exist for exactly the sessions in scope, with `passed` matching the rule. Trap: five of the thirteen built-ins only describe and leave `passed` empty. | manual labels; running over all 6,000 sessions |
| C2 | turn a finding into a check | Euro refund confirmations quote 100 times the amount. Write and register an evaluator that fails exactly those sessions. | W | The registered version, run by the grader on hidden labeled sessions (large legitimate dollar refunds, correct euro refunds, yen), reaches the thresholds. | fail every euro session; match session ids |
| C3 | the evaluator is wrong | `polite-closing` fails one session in twenty. Decide whether the agent is rude; repair whichever is at fault. | W | New evaluator version passes idle-timeout sessions and still fails the planted curt replies, on hidden sessions; the agent's repo is unchanged. | always pass; delete the evaluator |
| C4 | backfill one release | A second evaluator version exists; evaluate every session since 1.3.0 with it, and nothing earlier. | W | Coverage is exact in both directions; evaluator task count is bounded. | `--all` |
| C5 | agree with the reviewers | Forty sessions carry human verdicts. Make a registered evaluator agree with them and keep agreeing on sessions nobody reviewed. | W | Agreement ≥ 0.9 on the reviewed cohort and on a hidden reviewed set. | memorize the forty |
| C6 | check before merge | Write `bin/check.sh <cohort>` that runs the project's evaluators on a cohort and exits non-zero when the pass rate falls below a stated bar. | W | The grader calls it on two hidden cohorts, one good and one bad; exit codes and the stored evaluations agree. | hardcoded exit code |

### 9.4 Fix and replay (world `helpdesk-live`)

| id | title | what the agent must do | acceptance | shortcuts that must fail |
|---|---|---|---|---|
| F1 | replay without refunding anyone | Replay last week's refund sessions against version 1.6.1. | Replays completed with result sessions; the refund ledger has no new rows. Kitaru's default tool policy is `passthrough`, which runs the live tool. | default policy |
| F2 | fix the euro amounts, with evidence | Fix the fault, register a new version, show it works. | The grader's replay of hidden euro sessions against the newest version passes its evaluator; an experiment run by the agent exists on a cohort of at least 20 sessions with a higher result pass rate than baseline. | fix with no experiment; experiment on one session |
| F3 | the fix that breaks yen | As F2, instruction gives the symptom only. | Hidden sessions include a zero-decimal currency; the obvious fix fails it. | divide every amount by 100 |
| F4 | the experiment keeps failing | An experiment run fails every time. After the fix the agent calls a tool with new arguments, the `history` lookup misses, the policy says fail, and one failed replay fails the run. | Experiment run completed; ledger untouched; the side-effect tool is still not `passthrough`. | set every tool to `passthrough` |
| F5 | stop asking twice | The agent repeats a successful lookup. Remove the waste without removing useful repeats (retries after a timeout, re-polls of a changed status). | Grader's replay of hidden sessions: fewer tool calls on duplicate sessions, same calls on the two control groups, same final answers. | deduplicate every repeated call |
| F6 | run them together | Two independent lookups run one after the other; a third needs the second's result. Cut latency. | Hidden replays: node timings overlap for the independent pair, order kept for the dependent pair. | run all three together |
| F7 | where is the cheaper model safe? | Find the set of requests where the cheaper model gives the same result, and prove it. | A cohort that holds ≥ 0.9 of routine requests and no disputes; an experiment run on that cohort version with the model override whose pass rate is not below baseline. | cohort of everything |
| F8 | pick between two fixes | Two branches each claim to fix the fault. Register the better one as 1.7.0. | Grader's hidden replay against 1.7.0 passes; experiment runs for *both* candidates exist on the *same* cohort version. One branch wins only on the sessions its author chose. | pick by reading the code, no experiments |

### 9.5 Operate (world `helpdesk-live`)

| id | title | what the agent must do | acceptance |
|---|---|---|---|
| O1 | nothing is running | Evaluations and analyses have been queued for an hour. `bin/start_worker.sh` passes an explicit `--claim` list, which replaces the defaults, so the worker never takes those jobs. | The grader starts the worker with the script and submits one evaluation, one analysis and one replay: all complete. |
| O2 | record this agent | A PydanticAI agent runs but leaves nothing in Kitaru. Make it record under a named agent version. | The grader runs the entrypoint on hidden inputs: sessions appear with model and tool nodes, the right tool names, inputs and outputs. |
| O3 | make it replayable | Sessions are recorded but a replay request is rejected (422): the registered version has no run command and declares no replay capability. | The grader requests a replay of a hidden session with an override: it completes. |
| O4 | record a LangGraph agent | As O2 with `kitaru-langgraph`. Second adapter, so the set is not PydanticAI-only. **(spike: scripted chat model through this adapter)** | As O2. |

### 9.6 Not in the first set

- **A research-loop family** (the R1 analogue: "raise the pass rate within N experiment runs; the grader replays a hidden cohort"). With a scripted model the space of improvements is whatever we wrote into the script, so the task would test finding our switch. Worth doing only on the live-model track.
- **"Modernize a script that uses deprecated fields"** (`payload_blob_id`, `evaluate_baselines`, the `agent_version` worker label). The old fields still work, so doing nothing passes. Becomes a task on the release that removes them.
- **Anything needing a provider key**: the two OpenAI analyzers, the TypeSafe judge, provider-API imports, the Claude Agent SDK adapter, the hosted AI engineer.
- **TypeScript adapters** (Mastra, Vercel AI SDK): a second toolchain in the base image; later.

## 10. Conditions, generated instances, held-out set

- **Conditions** per task, as before: bare (CLI, SDK, docs snapshot) / + skills (`zenml-io/kitaru-skills` at a pinned commit, baked in because `kitaru setup` downloads them) / + MCP (`kitaru-mcp --mode standard` over stdio; note it does not follow the CLI's selected server and ignores `KITARU_API_TOKEN`). Kaizen's ZenML numbers are a warning to plan for: over 480 attempts, the MCP server and a skill raised cost and did not raise the score. Every instruction must say that a Kitaru workspace exists and where: without that sentence kaizen's bare agent answered from git in 26 of 36 attempts and never opened Kitaru.
- **Generated instances.** A world's `story.py` already takes a seed and parameters, so D1, C2 and I3 become families by varying what an agent has to find: which tool breaks, on which day, which two names collide, which currency. Seeds 0–4 committed as the held-out generated set, training seeds from 1000 regenerated on demand, as for `b10` and `b3`.
- **Private held-out set.** Kaizen's existing fixtures, unchanged and unpublished.
- **Model budget.** The rule in `CLAUDE.md` stands: baselines use Codex and OpenRouter models, no new Anthropic-model trials.
- **Attempts.** Kaizen found three attempts per task gave false signals that twenty corrected, and that eight tasks at five attempts detect only gaps of about 28 points. Budget k ≥ 5 per cell for anything that will be quoted, and compare a baseline against itself first.

## 11. The plan: levels and done bars

**Level 0 — spikes (nothing is built on a guess).** Each ends with a dated entry in `docs/decisions.md`.

1. Start Postgres, the server and a worker inside one container under `harbor run --agent nop` and under the verifiers runner; record what starts them and how long until `/health` answers.
2. Run a built-in evaluator and the JSONL importer with the network off, using a baked wheel directory.
3. Record 20 sessions from a PydanticAI agent with a scripted model, replay them with a `history` policy through a worker, five times; results identical.
4. Tamper inventory: what can be written through REST under `AUTH_SCHEME=none`, what through `psql`, and whether a second Unix user closes the second.
5. Template-database copy for a `grade_local.sh` that needs no Docker.
6. Read `zenml-io/agent-benchmarks`; settle section 8.

**Level 1 — one task end to end.** `kitaru/base/Dockerfile`, world `storefront` (story, loader, build-time self-check), `kitaru_checks.py`, task **C2** with reference, two alternatives, three shortcuts and the four checks; a first baseline (Codex, bare and + skills, k = 5); first entries in `docs/findings.md`. C2 is the right first task because it needs the whole machine except replay: a loaded world, a worker, a registered plugin, and a grader that re-runs the agent's work on hidden sessions. Done bar: `verify_task.py` green; `results/kitaru-level1.md` with the table and what the trajectories showed.

**Level 2 — imports, diagnosis, checks (20 tasks).** Worlds `clinic` and `exports`; I1–I5, D1–D9, C1–C6. Done bar: every task passes the four checks; baselines on two models; difficulty bands recorded; any task at 100 % on every model gets a harder variant or moves to a regression list.

**Level 3 — replay (12 tasks).** World `helpdesk-live` with the scripted model and the ledger service; F1–F8, O1–O4. Done bar: as Level 2, plus the oracle's replays are identical across five runs.

**Level 4 — publish.** Generators for three families; `registry.json` entry, `kitaru/dataset.toml`, Prime wrapper, prebuilt images; `check_public.sh` over everything; findings turned into Kitaru docs, CLI and MCP changes and re-run. The research for this proposal already found four stale docs passages that would trip an agent (a `kitaru context list` command that does not exist in `troubleshooting.md`; "five importers" where there are seven; the `analyzer` job kind missing from the worker claims list; the deprecated `payload_blob_id` still shown in `import-your-traces.md`).

## 12. Decisions for Alex

1. **Container arrangement** (section 4): A hardened toward C (recommended, keeps Prime), or B (cleaner, Harbor Hub only).
2. **Repository** (section 8): a `kitaru/` directory here (recommended), a new repo, or `zenml-io/agent-benchmarks`.
3. **Stories** (section 3): new public worlds with kaizen's kept private (recommended), or publish kaizen's after scrubbing.
4. **The model in the example agents** (section 5): scripted (recommended), or a live cheap model.
5. **Family D on a public leaderboard** (section 2): in, or kept as an internal regression set.
