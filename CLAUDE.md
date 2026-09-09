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
- Harbor `0.22.0` (not yet installed locally).

## Layout (grows as levels land; see brief section 9)

- `docs/` — brief, decisions, task-authoring guide, findings.
- `shared/projects/` — working example projects that tasks are generated from. `nightly/` is the B3 stale-cache project.
- `.venv/` — local dev environment: `uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python "zenml[local]==0.96.4" pandas scikit-learn`. Gitignored.

## Working conventions

- `uv run` / `uv pip`. PEP 723 metadata on standalone scripts. Type hints. Functional style.
- Before writing any grader assertion, run the reference solution by hand and inspect the ZenML store with `Client()` so assertions reflect observed state, not assumed API behaviour.
- Never grep an agent's source for the "right" line; grade what the ZenML store recorded.
- Set `ZENML_CONFIG_PATH` to a fresh directory for experiments so runs never touch the user's real ZenML config. `ZENML_ANALYTICS_OPT_IN=false`.
- Targeted `git add`; commit at natural pause points; backticks around identifiers in commit subjects. Never commit `jobs/`, raw trajectories, API keys, or anything under `design/`.
- Markdown: one paragraph per line, soft-wrapped.
- Subagents are welcome for parallel, independent work (docs lookups, spikes, baselines). The teaching rule applies to what the main agent relays back to Alex, not to subagent transcripts.
