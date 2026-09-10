# /// script
# requires-python = ">=3.14"
# ///
"""Run the harness × condition matrix for one task and collect results.

    uv run scripts/run_baselines.py tasks/b3-stale-cache --agent codex:gpt-5.4 --agent claude-code:claude-opus-5 \
        --condition bare --condition skill -k 3 --env-file .env

Conditions: bare (nothing extra), skill (`--skill <SKILL_SOURCE>`), mcp (`--mcp-config shared/mcp/zenml.json`: the ZenML
MCP server baked into the base image, talking to the container's local store over stdio; see docs/decisions.md 2026-09-10).
Writes results/<task>-baseline.jsonl via analyse_trajectories.py and prints a pass-rate table.

Open models through OpenRouter run on Harbor's own Terminus 2 harness (the model is called from the host, so the task's
network policy does not apply; `OPENROUTER_API_KEY` in .env):

    uv run scripts/run_baselines.py tasks/b4-nondeterministic-step --agent terminus-2:openrouter/qwen/qwen3.5-9b \
        -k 5 -n 2 --job-prefix small --name-with-model --ak max_turns=40 --ak record_terminal_session=false --env-file .env
"""
import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SKILLS_REPO = "https://github.com/zenml-io/skills"
SKILLS_SHA = "e8534cade92e1c0ce730e421de830509b04be6d2"  # pinned 2026-09-09; bump deliberately, note in decisions.md
# The repo is laid out as plugins (skills/<plugin>/skills/<skill>/SKILL.md), so we point Harbor at the
# inner skills/ dirs of the plugins relevant to pipeline work.
SKILL_DIRS = ["skills/zenml-pipeline-authoring/skills", "skills/zenml-quick-wins/skills"]
# Claude-style .mcp.json that Harbor merges into the agent's MCP servers at run time (`harbor run --mcp-config`), so
# task dirs stay condition-free. The server itself lives in the base image (shared/base/Dockerfile).
MCP_CONFIG = Path("shared/mcp/zenml.json")


def model_slug(model: str) -> str:
    """`openrouter/qwen/qwen3.5-9b` -> `qwen3.5-9b`: the last path segment, anything not [A-Za-z0-9.] becomes `-`."""
    import re
    return re.sub(r"[^A-Za-z0-9.]+", "-", model.rsplit("/", 1)[-1]).strip("-")


def skill_paths() -> list[str]:
    """Clone zenml-io/skills at the pinned SHA into .skills-cache/ (gitignored) and return the skill dirs."""
    cache = Path(".skills-cache") / f"zenml-io-skills-{SKILLS_SHA[:12]}"
    if not cache.exists():
        subprocess.run(["git", "clone", "-q", SKILLS_REPO, str(cache)], check=True)
        subprocess.run(["git", "-C", str(cache), "checkout", "-q", SKILLS_SHA], check=True)
    return [str(cache / d) for d in SKILL_DIRS]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", type=Path)
    ap.add_argument("--agent", action="append", required=True, help="harness or harness:model, e.g. codex or codex:gpt-5.4; no model = the CLI default")
    ap.add_argument("--condition", action="append", default=None, choices=["bare", "skill", "mcp"])
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("-n", type=int, default=None, help="Harbor concurrency (trials at once); default Harbor's")
    ap.add_argument("--env-file", type=Path, default=Path(".env"))
    ap.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    ap.add_argument("--label", default="", help="suffix for job names and the results file, e.g. cheap")
    ap.add_argument("--job-prefix", default="baseline", help="first token of job names and the results file (baseline-…); e.g. cmp for the comparison runs")
    ap.add_argument("--ak", action="append", default=[], help="agent kwarg passed through to `harbor run --ak key=value` (repeatable), e.g. --ak max_turns=50")
    ap.add_argument("--name-with-model", action="store_true",
                    help="put a slug of the model (its last path segment) into job names, so one harness can run several models in one results file")
    a = ap.parse_args()
    conditions = a.condition or ["bare"]
    jobs: list[tuple[str, str, str, Path]] = []
    for spec in a.agent:
        # First colon only: the model may itself contain slashes and colons (openrouter/qwen/qwen3.5-9b, qwen3.5-9b:batch).
        harness, _, model = spec.partition(":")
        harness_label = f"{harness}-{model_slug(model)}" if a.name_with_model and model else harness
        for cond in conditions:
            name = f"{a.job_prefix}-{a.task.name}-{harness_label}-{cond}" + (f"-{a.label}" if a.label else "")
            cmd = ["harbor", "run", "-p", str(a.task), "--agent", harness, *(["-m", model] if model else []), "-k", str(a.k),
                   "-o", str(a.jobs_dir), "--job-name", name, "--env-file", str(a.env_file), *(["-n", str(a.n)] if a.n else [])]
            for kw in a.ak:
                cmd += ["--ak", kw]
            if cond == "skill":
                for sp in skill_paths():
                    cmd += ["--skill", sp]
            if cond == "mcp":
                cmd += ["--mcp-config", str(MCP_CONFIG)]
            print("$", " ".join(cmd), flush=True)
            proc = subprocess.run(cmd)
            if proc.returncode != 0:
                print(f"harbor exited {proc.returncode} for {name}; continuing", file=sys.stderr)
            jobs.append((harness, model, cond, a.jobs_dir / name))

    out = Path("results") / (f"{a.task.name}-{a.job_prefix}-{a.label}.jsonl" if a.label else f"{a.task.name}-{a.job_prefix}.jsonl")
    import json
    # Merge into the existing results file: keep rows from jobs not run this time (e.g. bare/skill when adding mcp).
    fresh = Path(".") / f".{out.name}.tmp"
    subprocess.run([sys.executable, "scripts/analyse_trajectories.py", *[str(j[3]) for j in jobs], "--jsonl", str(fresh)], check=False)
    ran = {j[3].name for j in jobs}
    kept = [l for l in out.read_text().splitlines() if l.strip() and json.loads(l)["job"] not in ran] if out.exists() else []
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(l + "\n" for l in kept) + (fresh.read_text() if fresh.exists() else ""))
    fresh.unlink(missing_ok=True)
    print(f"\nrows written to {out} ({len(kept)} kept from earlier runs)\n")
    table: dict[tuple[str, str], list[float]] = defaultdict(list)
    for line in out.read_text().splitlines():
        r = json.loads(line)
        job = r["job"].removesuffix(f"-{a.label}") if a.label else r["job"]
        cond = job.rsplit("-", 1)[1]
        harness = job.removeprefix(f"{a.job_prefix}-{a.task.name}-").removesuffix(f"-{cond}")
        if r["reward"] is not None:
            table[(harness, cond)].append(float(r["reward"]))
    print(f"{'harness':<14}{'condition':<12}{'pass rate':<12}n")
    for (h, c), rs in sorted(table.items()):
        print(f"{h:<14}{c:<12}{sum(rs)/len(rs):<12.2f}{len(rs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
