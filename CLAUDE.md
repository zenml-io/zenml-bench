# zenml-bench — instructions for agents working in this repo

## What this is

A public benchmark of Harbor-format tasks where coding agents must build, fix, and research with real ZenML. The design brief is `docs/2026-09-09-plan.md`; read it once in full before doing anything. Decisions and resolved "(verify)" items go in `docs/decisions.md`, dated.

## Teach while you work (this is a hard rule)

Alex is building this partly to learn: Harbor, verifiers, RL environments, benchmark design, and the corners of ZenML the tasks exercise. Every session should leave him knowing something he did not know before.

- When you discover how a tool actually behaves (Harbor's reward file, ZenML's cache key, how the oracle agent runs), explain the mechanism in plain language at the moment you find it, not in a summary at the end. Use the `★ Insight` box format for this.
- Before a design choice with real trade-offs (how a grader checks state, how a fix should flow through a pipeline, which shortcut scripts to write), lay the options out as concrete states of the world and ask Alex to choose or to write the 5–15 lines that encode the choice. Prepare the file and the placeholder first so the contribution is small and well-framed.
- Explain the *why* behind benchmark-design rules when you apply them (grade recorded state not source text; hidden tests; the four verifier checks). Name the pattern so it can be recognised next time.
- Plain language, short sentences, concrete scenarios, named actors. Define any specialist term inline on first use. Alex's global `~/.claude/CLAUDE.md` has the full guidance on this and it applies here.
- Do not narrate process. "Now running the tests" is not teaching. "The test failed because ZenML gave the new artifact a new ID even though its contents were identical" is.

## Keep this file current

Any agent that adds a directory, a script, a convention, or resolves a decision must update this file (and `README.md` / `docs/` where relevant) in the same change. A stale CLAUDE.md is worse than none.

## Pinned versions (single source of truth: `docs/decisions.md`)

- ZenML `0.96.4` on Python `3.14`. The pin lives in exactly one place once `shared/base/Dockerfile` exists; read it from there everywhere else.
- Harbor `0.22.0`, installed with `uv tool install harbor==0.22.0`. Local task dirs run with `harbor run -p <dir> --agent oracle|nop|claude-code… -o jobs --job-name <name>`.

## Layout (grows as levels land; see brief section 9)

- `docs/` — brief, `decisions.md`, `task-authoring.md` (read before writing a task), `findings.md`.
- `shared/base/Dockerfile` — base image; the ZenML pin lives here (`ARG ZENML_PIN`).
- `shared/projects/` — working example projects that tasks are generated from. `nightly/` (B3), `legacy_training/` (B9, written in the 0.4x API on purpose), `k8s_training/` (B7), `churn_scoring/` (B5), `daily_report/` (B10; `README.md` there explains the scheduled/manual run naming). `nightly/make_data.py` and `daily_report/make_data.py` regenerate the shared fixtures.
- `tasks/<id>/` — Harbor tasks: `instruction.md`, `task.toml`, `environment/Dockerfile`, `solution/solve.sh` + `solution/alternatives/*.sh`, `tests/test.sh` + `tests/test_*.py` + `tests/fixtures/` + `tests/shortcuts/*.sh`. Solutions and shortcuts are bash scripts that patch the project in place and honour `APP_DIR`. A script that builds on the reference must locate it via `REF="$HERE/reference.sh"; [ -f "$REF" ] || REF="$HERE/../../solution/solve.sh"` (see decisions: self-recursion under Harbor). A grader may write extra numeric metrics to `/logs/verifier/metrics.json`; B5's `test.sh` merges them into `reward.json` so Harbor records them per trial. Optional `environment/setup_store.sh` registers stack components at image build and is also run by `grade_local.sh`. B10's `setup_store.sh` instead *runs the pipeline* several times to produce real run history and writes a `seed_runs.json` manifest next to the store (`$ZENML_CONFIG_PATH/` under `grade_local.sh`, `/var/lib/zenml-bench/` in the image). `grade_local.sh` takes repo-relative paths.
- `scripts/sync_project.sh <project> <task>` — copies a shared project into the task's `environment/` (Harbor builds from that dir alone). Run it after editing anything under `shared/projects/`; never edit the copy.
- `scripts/verify_task.py <task>` — the four verifier checks through Harbor (oracle ×5, nop, every shortcut, every alternative). Slow (~1 min per run); use `grade_local.sh` while iterating and this before calling a task done.
- `scripts/run_baselines.py <task> --agent harness:model --condition bare|skill -k 3 --env-file .env` — harness × condition matrix; writes `results/<task>-baseline.jsonl`.
- `scripts/analyse_trajectories.py jobs/<job>…` — per-trial: reward, infra_error, docs read, skill loaded, MCP calls, pipeline runs. v0; the docs/skill detection is by string markers in tool-call arguments.
- `.skills-cache/` — pinned clone of `zenml-io/skills` made by `run_baselines.py` (gitignored). Bump the SHA in that script deliberately.
- `docs/findings.md` — what baselines showed; each item should turn into a docs/skill/MCP/task fix and be re-run.
- `results/` — committed summaries only (jsonl/md). Raw `jobs/` is gitignored.
- `scripts/grade_local.sh <task> [patch.sh]` — runs a task's grader against a fresh copy of its project in a fresh ZenML store, no Docker. Use it to iterate on graders and to run the four checks before touching Harbor. `KEEP=1` keeps the temp dir, `VERBOSE=1` prints pytest failures.
- `.venv/` — local dev environment: `uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python "zenml[local]==0.96.4" pandas scikit-learn pytest`. Gitignored.

## Working conventions

- `uv run` / `uv pip`. PEP 723 metadata on standalone scripts. Type hints. Functional style.
- Before writing any grader assertion, run the reference solution by hand and inspect the ZenML store with `Client()` so assertions reflect observed state, not assumed API behaviour.
- Never grep an agent's source for the "right" line; grade what the ZenML store recorded.
- `docker build -t zenml-bench/base:0.96.4 shared/base` builds the base image every task `FROM`s. Rebuild after editing it.
- API keys live in `.env` at the repo root (gitignored): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. Harbor does not read it by itself; pass `--env-file .env` to `harbor run`. Never print or commit key values.
- Docker runtime: OrbStack (`docker context use orbstack`) is required for `no-network`/`allowlist`; Docker Desktop (`docker context use desktop-linux`) rejects them. Images are per-runtime; rebuild the base image after switching. Check `docker context ls` first if Harbor complains about network mode.
- Agent CLIs (claude-code, codex) are baked into the base image so setup needs no network. Harbor needs `-m <model>` for codex.
- Set `ZENML_CONFIG_PATH` to a fresh directory for experiments so runs never touch the user's real ZenML config. `ZENML_ANALYTICS_OPT_IN=false`.
- Targeted `git add`; commit at natural pause points; backticks around identifiers in commit subjects. Never commit `jobs/`, raw trajectories, API keys, or anything under `design/`.
- Markdown: one paragraph per line, soft-wrapped.
- Subagents are welcome for parallel, independent work (docs lookups, spikes, baselines). The teaching rule applies to what the main agent relays back to Alex, not to subagent transcripts.
