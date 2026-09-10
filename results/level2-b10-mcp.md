# Baseline — task B10 `why-did-it-fail`, "+ MCP" condition

Date: 2026-09-10. Same setup as `level2-b10.md` (Harbor 0.22.0, sealed network with the model API allowlisted, 3 attempts per cell) plus `--mcp-config shared/mcp/zenml.json`: the ZenML MCP server (`zenml-io/mcp-zenml` at `33c6c7f`, v1.2.0) baked into the base image and started over stdio by the agent CLI inside the container, reading the container's local SQLite store. Mechanism and pins in `docs/decisions.md` (2026-09-10). Raw rows: `b10-why-did-it-fail-baseline.jsonl` (`*-mcp` jobs) and `b10-why-did-it-fail-baseline-cheap.jsonl`. Bare and skill rows are copied from `level2-b10.md` for comparison.

| harness | model | condition | pass rate | called MCP | MCP tools called (per trial) | got `exception_info` via MCP | read log files on disk | tried a non-existent API | median tokens | mean cost |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | – | – | 0/3 | 2/3 | 3/3 (`step.logs`) | 476k | $0.58 |
| claude-code | claude-opus-5 | + skill | 3/3 | – | – | 0/3 | 2/3 | 3/3 (`step.logs`) | 445k | $0.49 |
| claude-code | claude-opus-5 | **+ MCP** | 3/3 | **3/3** | `list_pipeline_runs` ×2, `list_run_steps`, `get_step_logs` (+`list_pipelines` in 2) | **0/3** | 3/3 | **0/3** | 410k | $0.52 |
| codex | gpt-5.6-terra | bare | 3/3 | – | – | 1/3 | 3/3 | 2/3 (`runs describe`) | 271k | $0.19 |
| codex | gpt-5.6-terra | + skill | 3/3 | – | – | 3/3 | 2/3 | 3/3 (`runs describe`) | 383k | $0.23 |
| codex | gpt-5.6-terra | **+ MCP** | 3/3 | **0/3** | none | 0/3 (via MCP; 0/3 via Python either) | 3/3 | 3/3 (`runs describe`) | 242k | $0.15 |

Cheap tier (3 attempts each):

| harness | model | condition | pass rate | called MCP | MCP tools called | got `exception_info` via MCP | re-ran the failing day before reading the cause | median tokens | mean cost |
|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-haiku-4-5 | bare | 3/3 | – | – | – (2/3 via Python) | 2/3 | 709k | $0.14 |
| claude-code | claude-haiku-4-5 | + MCP | 2/3 | 1/3 | `list_pipeline_runs` ×2, `get_pipeline_run`, `list_run_steps`, `list_pipelines` | 0/3 | 1/3 | 842k | $0.14 |
| codex | gpt-5.4-mini | bare | 3/3 | – | – | – (3/3 via Python) | 0/3 | 349k | $0.10 |
| codex | gpt-5.4-mini | + MCP | 3/3 | 0/3 | none | 0/3 | 0/3 | 262k | $0.08 |

The haiku failure is the `.str` accessor trap on the second hidden fixture (a day with no separators makes `amount` a float column); a Codex smoke trial before the matrix failed the same way. Both are solution errors, not MCP effects. That haiku trial also deleted the seeded failed run "so we can retry with the same name", which the instruction forbids.

## What the MCP changed, and what it did not

**Claude Code picked the tools up immediately and stopped guessing.** Every opus trial's first move after reading `run.py` was a `ToolSearch` for five `mcp__zenml__*` tools by name (Claude Code 2.1 keeps MCP tools deferred until searched; the trial saw "64 deferred tools"), then `list_pipeline_runs(size=20)` → `list_run_steps(pipeline_run_id=…)` → `get_step_logs(step_run_id=…)`. The `StepRunResponse.logs` guess that appeared in 6/6 bare and skill trials is gone (0/3): with a tool list in front of it, the model picked a tool instead of inventing an attribute. Tokens and cost are level with bare (410k vs 476k median; $0.52 vs $0.58).

**But the tool it picked is the one that needs a server, and the tool that has the answer does not say so.** `get_step_logs` calls the ZenML REST API and returns `{"error": {"type": "ConfigurationError", "missing_env_var": "ZENML_STORE_URL"}}` against a local store. All three opus trials hit that error, then went to the store's log files on disk (`/root/.config/zenml/local_stores/<id>/logs/<step>.log`), exactly as in the bare condition. None called `get_run_step`, whose description is "Get a run step by name, ID, or prefix" and whose 9 KB JSON response carries `metadata.exception_info` with the traceback, exception class, message and failing line. So the "found `exception_info`" column stays at 0/3 for opus: the MCP has the data but no tool whose name or description says "why did this step fail", and the tool whose name says "logs" is the wrong one offline.

**Codex never opened the MCP.** 0/6 Codex trials (terra and mini) made an MCP call, in the same trials where Codex still ran `zenml pipeline runs describe` (3/3 terra), a command that does not exist. A probe trial through Harbor whose instruction asked for the MCP tools by name showed Codex sees the server (`mcp__zenml`, all 50 tools) and can call them, so this is a choice, not a delivery failure. Codex 0.153 exposes MCP tools behind a `tool_search` step and only searches when it decides it lacks a tool; with a `zenml` CLI in the shell it never decided that. Same pattern as the skill condition, where Claude Code chose not to invoke the skill: the harness's discovery mechanism, not the content, decides whether a condition is even exercised.

**Cheap tier.** Haiku used the MCP in 1/3 trials (and that trial found the run and step through it before reading the CSV); the other two behaved like bare haiku, including one that re-ran the failing day to see the error. gpt-5.4-mini 0/3, like terra.

## Findings

1. **Missing tool, stated exactly** (`docs/findings.md`): a `get_step_failure(step_run_id)` (or `get_run_failures(pipeline_run_id)`) that returns `{step, status, exception_info: {source, message, traceback, user_code_line}}` for each failed step, and `get_run_step`'s description should mention that it includes `exception_info` for failed steps. `get_step_logs` should fall back to the local log file (`step.resources.log_collection[*].uri`) when `ZENML_STORE_URL` is unset instead of erroring.
2. **The MCP condition measures tool discovery as much as tool value.** For Claude Code the discovery is by name (ToolSearch), so tool names matter more than descriptions; for Codex the whole server sits behind one search that the model has to want to run. Any MCP finding on this benchmark has to be read per harness.
3. **B10 is still saturated** under this condition (11/12, one solution error). The instrumented columns (`mcp_calls`, `mcp_tools`, `mcp_exception_info`, on-disk log reads, non-existent API calls) are where the signal is; the reward is not.
4. Spend for the condition: about $3.5 (12 trials, 2 smoke trials, 3 probes).
