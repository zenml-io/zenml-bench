# /// script
# requires-python = ">=3.14"
# ///
"""The four verifier checks for one task, run through Harbor (brief §7.4).

    uv run scripts/verify_task.py tasks/b3-stale-cache [--oracle-attempts 5] [--jobs-dir jobs] [-n 2]

1. oracle (solution/solve.sh) scores 1.0 on every attempt
2. the `nop` agent (does nothing) scores 0
3. every tests/shortcuts/*.sh scores 0
4. every solution/alternatives/*.sh scores 1.0

Shortcuts and alternatives are run by copying the task to a temp dir with that script installed as
solution/solve.sh and running Harbor's oracle agent, so all checks share one container path.
Exit code 1 if any check fails.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def harbor_rewards(task_dir: Path, agent: str, attempts: int, jobs_dir: Path, name: str, n_concurrent: int | None = None) -> list[float]:
    job = jobs_dir / name
    shutil.rmtree(job, ignore_errors=True)
    cmd = ["harbor", "run", "-p", str(task_dir), "--agent", agent, "-k", str(attempts), "-o", str(jobs_dir), "--job-name", name, *(["-n", str(n_concurrent)] if n_concurrent else [])]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-3000:], proc.stderr[-3000:], file=sys.stderr)
        raise SystemExit(f"harbor run failed for {name}")
    results = sorted(job.glob("*/result.json"))
    rewards = []
    for p in results:
        vr = json.loads(p.read_text()).get("verifier_result") or {}
        r = (vr.get("rewards") or {}).get("reward")
        rewards.append(float(r) if r is not None else float("nan"))  # nan = trial crashed (infra/agent exception)
    return rewards


def with_solution(task_dir: Path, script: Path, tmp: Path) -> Path:
    copy = tmp / task_dir.name
    shutil.copytree(task_dir, copy, ignore=shutil.ignore_patterns(".zen", "__pycache__"))
    shutil.copy(task_dir / "solution" / "solve.sh", copy / "solution" / "reference.sh")  # so scripts that build on the reference can find it
    shutil.copy(script, copy / "solution" / "solve.sh")
    return copy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", type=Path)
    ap.add_argument("--oracle-attempts", type=int, default=5)
    ap.add_argument("-n", type=int, default=None, help="Harbor concurrency (trials at once); default Harbor's (4)")
    ap.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    a = ap.parse_args()
    task, prefix = a.task.resolve(), f"verify-{a.task.name}"
    checks: list[tuple[str, list[float], float]] = []  # (label, rewards, expected)

    checks.append(("oracle", harbor_rewards(task, "oracle", a.oracle_attempts, a.jobs_dir, f"{prefix}-oracle", a.n), 1.0))
    checks.append(("nop", harbor_rewards(task, "nop", 1, a.jobs_dir, f"{prefix}-nop"), 0.0))
    with tempfile.TemporaryDirectory() as tmp_s:
        for kind, expected in (("tests/shortcuts", 0.0), ("solution/alternatives", 1.0)):
            for script in sorted((task / kind).glob("*.sh")):
                copy = with_solution(task, script, Path(tmp_s) / script.stem)
                label = f"{kind.split('/')[-1]}/{script.name}"
                checks.append((label, harbor_rewards(copy, "oracle", 1, a.jobs_dir, f"{prefix}-{script.stem}"), expected))

    ok = True
    print(f"\n{'check':<45} {'rewards':<22} expected  status")
    for label, rewards, expected in checks:
        passed = bool(rewards) and all(r == expected for r in rewards)
        ok &= passed
        print(f"{label:<45} {str(rewards):<22} {expected:<9} {'PASS' if passed else 'FAIL'}")
    print("\nALL FOUR CHECKS PASS" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
