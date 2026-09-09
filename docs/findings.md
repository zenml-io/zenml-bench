# Findings from baselines

What agents actually did, what broke, and what it points at (docs, skill, MCP, or our own task). Newest at the bottom. Feed each item into a fix and re-run the task that exposed it.

## 2026-09-09 — first Codex trial on B3 (gpt-5.6-terra, bare, 1 attempt)

- **Outcome:** correct fix, scored 0 because of a grader bug. Codex computed a SHA-256 of the data file in the pipeline function body and passed it into `load_data` as a parameter: a valid fourth solution (not one of our three). It read `/opt/zenml-docs/llms-full.txt` with `rg` for "cache" and "file", ran the pipeline five times, edited the CSV to test, restored it, and explained the mechanism correctly in its final message.
- **Grader bug:** the test asserted `train` executed on the grader's first run (dataset a). The agent had already run the fixed pipeline on dataset a, the ZenML store is shared between agent and grader, so the first run was a legitimate cache hit. Fixed by dropping that assertion; `solution/alternatives/solve_then_run_twice.sh` now guards it. **General rule for graders:** anything the agent could have run before grading may be cached; only assert "executed" on inputs the agent has never seen.
- **Instrumentation:** `docs_read=True`, `pipeline_runs=5`, `steps=18`, `tool_calls=12` from `analyse_trajectories.py`. Codex's tool calls are JavaScript `exec` blocks wrapping `tools.exec_command` and `tools.apply_patch`, so the string markers worked but the `pipeline_runs` count includes the agent's own test runs.
