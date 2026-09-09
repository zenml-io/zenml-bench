# /// script
# requires-python = ">=3.14"
# ///
"""v0: what did the agent do? Reads Harbor job dirs and prints one row per trial.

    uv run scripts/analyse_trajectories.py jobs/<job> [jobs/<job2> ...] [--jsonl out.jsonl]

Per trial: reward, infra_error, steps, tool calls, whether the offline docs were read, whether a
skill file was read, MCP calls, entrypoint invocations (`pipeline_runs`: counts tool calls that invoke a project entrypoint, incl. the agent's own test runs). Trajectories are ATIF (`agent/trajectory.json`).
"""
import argparse
import json
from pathlib import Path
from typing import Any

DOCS_MARKERS = ("/opt/zenml-docs", "llms-full.txt")
ENTRYPOINTS = ("run.py", "research.py", "train.py")  # project entrypoints: nightly/k8s/legacy/churn, research, research_bare
SKILL_MARKERS = ("SKILL.md", "/harbor/skills", "/.agents/skills", ".claude/skills", "CLAUDE_CONFIG_DIR/skills")


def blob(call: dict[str, Any]) -> str:
    return json.dumps(call.get("arguments", {}), ensure_ascii=False)


def summarise(trial: Path) -> dict[str, Any]:
    result = json.loads((trial / "result.json").read_text())
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    row: dict[str, Any] = {
        "trial": trial.name,
        "agent": (result.get("agent_info") or {}).get("name") or result.get("agent_name"),
        "model": (result.get("agent_info") or {}).get("model_name") or result.get("model_name"),
        "reward": rewards.get("reward"),
        "infra_error": bool(result.get("exception_info")) and rewards.get("reward") is None,
        "steps": 0, "tool_calls": 0, "docs_read": False, "skill_loaded": False, "mcp_calls": 0, "pipeline_runs": 0,
    }
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
            row["mcp_calls"] += name.startswith("mcp") or "mcp__" in name
            row["pipeline_runs"] += any(e in args for e in ENTRYPOINTS) and ("python" in args or "uv run" in args)
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
    cols = ["job", "trial", "reward", "infra_error", "steps", "tool_calls", "docs_read", "skill_loaded", "mcp_calls", "pipeline_runs"]
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(r.get(c)) for c in cols))
    if a.jsonl:
        a.jsonl.parent.mkdir(parents=True, exist_ok=True)
        a.jsonl.write_text("".join(json.dumps(r) + "\n" for r in rows))


if __name__ == "__main__":
    main()
