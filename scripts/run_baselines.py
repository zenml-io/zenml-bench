# /// script
# requires-python = ">=3.14"
# ///
"""Run the harness × condition matrix for one task and collect results.

    uv run scripts/run_baselines.py tasks/b3-stale-cache --agent codex:gpt-5.4 --agent claude-code:claude-opus-5 \
        --condition bare --condition skill -k 3 --env-file .env

Conditions: bare (nothing extra), skill (`--skill <SKILL_SOURCE>`), mcp (not wired yet).
Writes results/<task>-baseline.jsonl via analyse_trajectories.py and prints a pass-rate table.
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
    ap.add_argument("--env-file", type=Path, default=Path(".env"))
    ap.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    a = ap.parse_args()
    conditions = a.condition or ["bare"]
    jobs: list[tuple[str, str, str, Path]] = []
    for spec in a.agent:
        harness, _, model = spec.partition(":")
        for cond in conditions:
            name = f"baseline-{a.task.name}-{harness}-{cond}"
            cmd = ["harbor", "run", "-p", str(a.task), "--agent", harness, *(["-m", model] if model else []), "-k", str(a.k),
                   "-o", str(a.jobs_dir), "--job-name", name, "--env-file", str(a.env_file)]
            if cond == "skill":
                for sp in skill_paths():
                    cmd += ["--skill", sp]
            if cond == "mcp":
                raise SystemExit("mcp condition needs [[environment.mcp_servers]] in the task; not wired yet")
            print("$", " ".join(cmd), flush=True)
            proc = subprocess.run(cmd)
            if proc.returncode != 0:
                print(f"harbor exited {proc.returncode} for {name}; continuing", file=sys.stderr)
            jobs.append((harness, model, cond, a.jobs_dir / name))

    out = Path("results") / f"{a.task.name}-baseline.jsonl"
    subprocess.run([sys.executable, "scripts/analyse_trajectories.py", *[str(j[3]) for j in jobs], "--jsonl", str(out)], check=False)
    print(f"\nrows written to {out}\n")
    import json
    table: dict[tuple[str, str], list[float]] = defaultdict(list)
    for line in out.read_text().splitlines():
        r = json.loads(line)
        cond = r["job"].rsplit("-", 1)[1]
        harness = r["job"].removeprefix(f"baseline-{a.task.name}-").removesuffix(f"-{cond}")
        if r["reward"] is not None:
            table[(harness, cond)].append(float(r["reward"]))
    print(f"{'harness':<14}{'condition':<12}{'pass rate':<12}n")
    for (h, c), rs in sorted(table.items()):
        print(f"{h:<14}{c:<12}{sum(rs)/len(rs):<12.2f}{len(rs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
