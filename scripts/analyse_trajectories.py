# /// script
# requires-python = ">=3.14"
# ///
"""v0: what did the agent do? Reads Harbor job dirs and prints one row per trial.

    uv run scripts/analyse_trajectories.py jobs/<job> [jobs/<job2> ...] [--jsonl out.jsonl]

Per trial: reward, infra_error, steps, tool calls, whether the offline docs were read, whether a
skill file was read, MCP calls (`mcp_calls` total, `mcp_tools` per tool name, `mcp_exception_info` when an MCP result carried a
step's `exception_info` traceback), entrypoint invocations (`pipeline_runs`: counts tool calls that invoke a project entrypoint, incl. the agent's own test runs), off-loop scripts (`scripts`: tool calls that run Python without an entrypoint), `agent_minutes` (agent-phase wall clock from result.json) and `first_run_s` (seconds from the agent's start to its first entrypoint call). Trajectories are ATIF (`agent/trajectory.json`).
"""
from datetime import datetime
import argparse
import json
from pathlib import Path
from typing import Any

DOCS_MARKERS = ("/opt/zenml-docs", "llms-full.txt")
ENTRYPOINTS = ("run.py", "research.py", "train.py")  # project entrypoints: nightly/k8s/legacy/churn, research, research_bare
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
        "model": (result.get("agent_info") or {}).get("model_name") or result.get("model_name"),
        "reward": rewards.get("reward"),
        "infra_error": bool(result.get("exception_info")) and rewards.get("reward") is None,
        "steps": 0, "tool_calls": 0, "docs_read": False, "skill_loaded": False, "mcp_calls": 0, "mcp_tools": {},
        "mcp_exception_info": False, "pipeline_runs": 0, "scripts": 0, "agent_minutes": None, "first_run_s": None,
    }
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
        for call in step.get("tool_calls") or []:
            row["tool_calls"] += 1
            name, args = call.get("function_name", ""), blob(call)
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
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="+", type=Path)
    ap.add_argument("--jsonl", type=Path)
    a = ap.parse_args()
    rows = [summarise(t) | {"job": job.name} for job in a.jobs for t in sorted(job.iterdir()) if (t / "result.json").exists()]
    cols = ["job", "trial", "reward", "infra_error", "steps", "tool_calls", "docs_read", "skill_loaded", "mcp_calls", "mcp_exception_info", "pipeline_runs", "scripts", "agent_minutes", "first_run_s"]
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(r.get(c)) for c in cols))
    if a.jsonl:
        a.jsonl.parent.mkdir(parents=True, exist_ok=True)
        a.jsonl.write_text("".join(json.dumps(r) + "\n" for r in rows))


if __name__ == "__main__":
    main()
