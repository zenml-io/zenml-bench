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

SKILL_SOURCE = "zenml-io/skills"  # git source; pin to a commit once Harbor's syntax for that is confirmed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", type=Path)
    ap.add_argument("--agent", action="append", required=True, help="harness:model, e.g. codex:gpt-5.4")
    ap.add_argument("--condition", action="append", default=None, choices=["bare", "skill", "mcp"])
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--env-file", type=Path, default=Path(".env"))
    ap.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    a = ap.parse_args()
    conditions = a.condition or ["bare"]
    jobs: list[tuple[str, str, str, Path]] = []
    for spec in a.agent:
        harness, model = spec.split(":", 1)
        for cond in conditions:
            name = f"baseline-{a.task.name}-{harness}-{cond}"
            cmd = ["harbor", "run", "-p", str(a.task), "--agent", harness, "-m", model, "-k", str(a.k),
                   "-o", str(a.jobs_dir), "--job-name", name, "--env-file", str(a.env_file)]
            if cond == "skill":
                cmd += ["--skill", SKILL_SOURCE]
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
        harness, cond = r["job"].split("-")[-2:]
        if r["reward"] is not None:
            table[(harness, cond)].append(float(r["reward"]))
    print(f"{'harness':<14}{'condition':<12}{'pass rate':<12}n")
    for (h, c), rs in sorted(table.items()):
        print(f"{h:<14}{c:<12}{sum(rs)/len(rs):<12.2f}{len(rs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
