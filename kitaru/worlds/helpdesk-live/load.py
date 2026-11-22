"""Record the helpdesk history by running the assistant, once per request, while the image is built. Runs as root.

Registers the agent with one version per release (each with its own directory, because an agent version is a run
command and a directory, not a copy of the code), runs every planned request through the release that served it,
registers the team's evaluator, builds the cohort the replay tasks start from, commits the workspace, and writes what
the grader needs to compare against to a file only root can read."""
import gzip
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

WORLD, APP = Path(__file__).parent, Path("/app")
RELEASES = ["1.6.0", "1.6.1"]
TOOLS = [x for t in ("lookup_order", "lookup_customer", "check_return_policy", "get_shipping_status", "issue_refund", "escalate_to_human") for x in ("--tool", t)]
FINANCE = Path("/var/lib/helpdesk-finance")


def kitaru(*args: str) -> dict[str, Any]:
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        data = {"ok": False, "error": (out.stdout + out.stderr)[-1500:]}
    if not data.get("ok"):
        sys.exit(f"kitaru {' '.join(args)} failed: {json.dumps(data.get('error'))[:1500]}")
    return data


def rows(name: str) -> int:
    path = FINANCE / f"{name}.jsonl"
    return len(path.read_text().splitlines()) if path.exists() else 0


def main() -> None:
    plan = json.loads((WORLD / "plan.json").read_text())
    requests = [json.loads(line) for line in gzip.open(WORLD / "sessions-requests.jsonl.gz", "rt")]
    agent = kitaru("agent", "register", "helpdesk-agent", "--description", "Larkspur Goods helpdesk assistant: refunds, parcel status, disputes.", "--display-version", RELEASES[0],
                   "--command", "python -m helpdesk.agent", "--working-dir", f"/app/releases/{RELEASES[0]}", *TOOLS)["item"]
    versions = {RELEASES[0]: agent["version"]["id"]}
    for release in RELEASES[1:]:
        versions[release] = kitaru("agent", "version", "register", "helpdesk-agent", "--display-version", release, "--command", "python -m helpdesk.agent",
                                   "--working-dir", f"/app/releases/{release}", *TOOLS)["item"]["version"]["id"]
    agent_id = agent["agent"]["id"]

    def record(request: dict[str, Any]) -> None:
        env = {**os.environ, "KITARU_AGENT_ID": agent_id, "KITARU_AGENT_VERSION_ID": versions[request["release"]], "KITARU_SESSION_NAME": request["id"]}
        out = subprocess.run([sys.executable, "-m", "helpdesk.agent", request["prompt"]], cwd=f"/app/releases/{request['release']}", env=env, capture_output=True, text=True)
        if out.returncode:
            sys.exit(f"recording {request['id']} failed: {out.stderr[-800:]}")

    t0 = time.time()
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(record, requests))
    sessions = {s["name"]: s for s in kitaru("session", "list", "--size", "1000")["items"]}
    created = {v: sum(1 for s in sessions.values() if s["agent_version_id"] == i) for v, i in versions.items()}
    print(f"recorded {len(sessions)} sessions in {time.time() - t0:.0f}s: {created}; refunds {rows('refunds')}, escalations {rows('escalations')}", flush=True)
    if created != plan["by_version"] or set(sessions) != {r["id"] for r in requests}:
        sys.exit(f"server holds {created}, the plan says {plan['by_version']}")

    kitaru("evaluator", "register", "refund-once", "--script", "/app/evaluators/refund_once.py", "--entrypoint", "evaluate", "--description", "Passes when a conversation issued at most one refund.")
    name = next(r["cohort"] for r in requests if r["cohort"])
    members = [sessions[r["id"]]["id"] for r in requests if r["cohort"]]
    Path("/tmp/cohort.txt").write_text("\n".join(members) + "\n")
    kitaru("cohort", "create", name, "--agent", "helpdesk-agent", "--sessions-file", "/tmp/cohort.txt", "--description", "Refunds issued by release 1.6.0 that the team wants to run again under 1.6.1.")

    subprocess.run(["chown", "-R", "agent:agent", str(APP)], check=True)
    subprocess.run(["runuser", "-u", "agent", "--", "sh", "-c", "cd /app && find . -name __pycache__ -prune -exec rm -rf {} + ; git init -q -b main && git add -A && "
                    "git -c user.name=larkspur -c user.email=dev@larkspur.example commit -q -m 'Helpdesk assistant: releases 1.6.0 and 1.6.1'"], check=True)
    head = subprocess.run(["git", "-c", "safe.directory=/app", "-C", "/app", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    Path("/etc/kitaru-bench/helpdesk.json").write_text(json.dumps({
        "agent_id": agent_id, "versions": versions, "sessions": {name: s["id"] for name, s in sessions.items()}, "cohort_id": kitaru("cohort", "get", name)["item"]["id"],
        "cohort_members": sorted(members), "refund_rows": rows("refunds"), "escalation_rows": rows("escalations"), "head": head}))
    os.chmod("/etc/kitaru-bench/helpdesk.json", 0o600)  # the grader's record of the starting state; root only


if __name__ == "__main__":
    main()
