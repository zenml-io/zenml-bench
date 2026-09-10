# /// script
# requires-python = ">=3.14"
# ///
"""v0: what did the agent do? Reads Harbor job dirs and prints one row per trial.

    uv run scripts/analyse_trajectories.py jobs/<job> [jobs/<job2> ...] [--jsonl out.jsonl]

Per trial: reward, infra_error, steps, tool calls, whether the offline docs were read, whether a
skill file was read, MCP calls (`mcp_calls` total, `mcp_tools` per tool name, `mcp_exception_info` when an MCP result carried a
step's `exception_info` traceback), entrypoint invocations (`pipeline_runs`: counts tool calls that invoke a project entrypoint, incl. the agent's own test runs), off-loop scripts (`scripts`: tool calls that run Python without an entrypoint), `agent_minutes` (agent-phase wall clock from result.json) and `first_run_s` (seconds from the agent's start to its first entrypoint call). Trajectories are ATIF (`agent/trajectory.json`).

Terminus 2 rows (harness the RL notes train through; `docs/decisions.md` 2026-09-10) also carry `turns` (model calls), `parse_errors`
(responses Terminus could not parse into commands), `task_complete` (the agent said it was done), `summarizations` (context
compactions Terminus ran because the model's window filled), `cmd_timeouts` (commands still running when their wait expired),
`timed_out` (Harbor killed the agent at `[agent] timeout_sec`), `max_prompt_tokens` (largest single prompt, i.e. the context window a trainer would need) and, for reward 0, `failure_class` (see `classify`).
"""
from datetime import datetime
import argparse
import json
from pathlib import Path
from typing import Any

DOCS_MARKERS = ("/opt/zenml-docs", "llms-full.txt")
ENTRYPOINTS = ("run.py", "research.py", "train.py", "inference.py", "pipelines/daily.py", "region_report.py", "report.py", "serve.py", "training.py")  # every `python <x>.py` named in tasks/*/instruction.md
EXC_MARKER = '"exception_info": {'  # a non-null ExceptionInfo in a serialised StepRunResponse
SKILL_MARKERS = ("SKILL.md", "/harbor/skills", "/.agents/skills", ".claude/skills", "CLAUDE_CONFIG_DIR/skills")


def parse_ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def blob(call: dict[str, Any]) -> str:
    return json.dumps(call.get("arguments", {}), ensure_ascii=False)


# Tool names of the pinned zenml-io/mcp-zenml server (`tools/list`; see shared/base/Dockerfile for the SHA). Needed
# because Codex's rollout records an MCP call as `function_call` name=<tool>, namespace="mcp__zenml", and Harbor's
# ATIF conversion keeps only the name; Claude Code records `mcp__zenml__<tool>`.
ZENML_MCP_TOOLS = frozenset("""diagnose_zenml_setup get_step_logs list_users get_user get_active_user get_active_project
get_project list_projects get_stack easter_egg list_stacks list_pipelines get_pipeline_details get_service list_services
get_stack_component list_stack_components get_flavor list_flavors trigger_pipeline get_run_template list_run_templates
get_snapshot list_snapshots get_deployment list_deployments get_deployment_logs get_schedule list_schedules
get_pipeline_run list_pipeline_runs get_run_step list_run_steps list_artifacts get_artifact_version
list_artifact_versions list_secrets get_service_connector list_service_connectors get_model list_models
get_model_version list_model_versions get_step_code get_tag list_tags get_build list_builds
open_pipeline_run_dashboard open_run_activity_chart""".split())


def mcp_tool_name(function_name: str) -> str | None:
    """Return the bare MCP tool name for an MCP call, else None (see ZENML_MCP_TOOLS for why both forms)."""
    if function_name.startswith("mcp__"):
        return function_name.split("__", 2)[-1]
    return function_name if function_name in ZENML_MCP_TOOLS else None


def observations(step: dict[str, Any], call: dict[str, Any]) -> list[dict[str, Any]]:
    """The tool results in this step that answer `call` (matched by id when present, else all of them)."""
    results = (step.get("observation") or {}).get("results") or []
    mine = [r for r in results if r.get("source_call_id") == call.get("tool_call_id")]
    return mine or results


def summarise(trial: Path) -> dict[str, Any]:
    result = json.loads((trial / "result.json").read_text())
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    row: dict[str, Any] = {
        "trial": trial.name,
        "agent": (result.get("agent_info") or {}).get("name") or result.get("agent_name"),
        # Harbor 0.22 records the model under config.agent.model_name (and agent_info.model_info.name); agent_info.model_name is never set.
        "model": ((result.get("config") or {}).get("agent") or {}).get("model_name")
        or ((result.get("agent_info") or {}).get("model_info") or {}).get("name"),
        "reward": rewards.get("reward"),
        "infra_error": bool(result.get("exception_info")) and rewards.get("reward") is None,
        "steps": 0, "tool_calls": 0, "docs_read": False, "skill_loaded": False, "mcp_calls": 0, "mcp_tools": {},
        "mcp_exception_info": False, "pipeline_runs": 0, "scripts": 0, "agent_minutes": None, "first_run_s": None,
        "turns": 0, "parse_errors": 0, "task_complete": False, "summarizations": 0, "cmd_timeouts": 0, "timed_out": False,
        "max_turns": None, "max_prompt_tokens": 0,  # largest single prompt: the window a trainer would need
    }
    exc = result.get("exception_info") or {}
    row["timed_out"] = "Timeout" in (exc.get("exception_type") or "")
    row["summarizations"] = ((result.get("agent_result") or {}).get("metadata") or {}).get("summarization_count") or 0
    try:  # the cap we ran with, if any (`--ak max_turns=N` lands in the trial config)
        row["max_turns"] = (json.loads((trial / "config.json").read_text()).get("agent") or {}).get("kwargs", {}).get("max_turns")
    except (OSError, ValueError):
        pass
    ae = result.get("agent_execution") or {}
    started = parse_ts(ae.get("started_at"))
    if started and (finished := parse_ts(ae.get("finished_at"))):
        row["agent_minutes"] = round((finished - started).total_seconds() / 60, 1)
    traj = trial / "agent" / "trajectory.json"
    if not traj.exists():
        return row
    t = json.loads(traj.read_text())
    for step in t.get("steps", []):
        row["steps"] += 1
        row["turns"] += step.get("source") == "agent"
        row["max_prompt_tokens"] = max(row["max_prompt_tokens"], (step.get("metrics") or {}).get("prompt_tokens") or 0)
        obs_text = " ".join(r.get("content") or "" for r in (step.get("observation") or {}).get("results") or [])
        row["parse_errors"] += obs_text.startswith("Previous response had parsing errors")
        row["cmd_timeouts"] += "timed out after" in obs_text
        for call in step.get("tool_calls") or []:
            row["tool_calls"] += 1
            name, args = call.get("function_name", ""), blob(call)
            row["task_complete"] |= name == "mark_task_complete"
            row["docs_read"] |= any(m in args for m in DOCS_MARKERS)
            row["skill_loaded"] |= name == "Skill" or any(m in args for m in SKILL_MARKERS)
            if tool := mcp_tool_name(name):
                row["mcp_calls"] += 1
                row["mcp_tools"][tool] = row["mcp_tools"].get(tool, 0) + 1
                row["mcp_exception_info"] |= any(EXC_MARKER in r.get("content", "") for r in observations(step, call))
            runs_python = "python" in args or "uv run" in args
            is_run = any(e in args for e in ENTRYPOINTS) and runs_python
            row["pipeline_runs"] += is_run
            row["scripts"] += runs_python and not is_run
            if is_run and row["first_run_s"] is None and started and (ts := parse_ts(step.get("timestamp"))):
                row["first_run_s"] = round((ts - started).total_seconds())
    fm = t.get("final_metrics") or {}
    row["total_tokens"] = (fm.get("total_prompt_tokens") or 0) + (fm.get("total_completion_tokens") or 0) or None
    row["cost_usd"] = fm.get("total_cost_usd")
    if not row["reward"]:
        row["failure_class"] = classify(row)
    return row


def classify(row: dict[str, Any]) -> str:
    """One label per failed trial, first match wins. Order matters: a trial that both overflowed and never ran the
    pipeline is an overflow, because that is what stopped it."""
    if row["infra_error"]:
        return "infra_error"
    if row["timed_out"]:
        return "timeout"
    if row["summarizations"]:
        return "context_overflow"
    if row["max_turns"] and row["turns"] >= row["max_turns"] and not row["task_complete"]:
        return "max_turns"
    if row["pipeline_runs"] == 0:
        return "format" if row["parse_errors"] >= 3 else "never_ran_pipeline"
    return "wrong_fix" if row["task_complete"] else "gave_up"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="+", type=Path)
    ap.add_argument("--jsonl", type=Path)
    a = ap.parse_args()
    rows = [summarise(t) | {"job": job.name} for job in a.jobs for t in sorted(job.iterdir()) if (t / "result.json").exists()]
    cols = ["job", "trial", "reward", "infra_error", "steps", "tool_calls", "docs_read", "skill_loaded", "mcp_calls", "mcp_exception_info", "pipeline_runs", "scripts", "agent_minutes", "first_run_s"]
    if any(r["turns"] for r in rows):
        cols += ["turns", "parse_errors", "task_complete", "summarizations", "cmd_timeouts", "timed_out", "failure_class"]
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(r.get(c)) for c in cols))
    if a.jsonl:
        a.jsonl.parent.mkdir(parents=True, exist_ok=True)
        a.jsonl.write_text("".join(json.dumps(r) + "\n" for r in rows))


if __name__ == "__main__":
    main()
