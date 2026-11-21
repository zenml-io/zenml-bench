"""Record the helpdesk history by running the assistant, once per request, while the image is built. Runs as root.

Registers the agent with one version (release 2.0.0, run from its own directory), runs every planned request through
it against the order service and the finance service, registers the team's evaluator, commits the workspace, and
writes what the grader needs to compare against to a file only root can read."""
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
RELEASE = "2.0.0"
TOOLS = [x for t in ("lookup_order", "lookup_customer", "check_return_policy", "get_shipping_status", "issue_refund", "escalate_to_human") for x in ("--tool", t)]
FINANCE, ORDERS = Path("/var/lib/helpdesk-finance"), Path("/var/lib/helpdesk-orders")


def kitaru(*args: str) -> dict[str, Any]:
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        data = {"ok": False, "error": (out.stdout + out.stderr)[-1500:]}
    if not data.get("ok"):
        sys.exit(f"kitaru {' '.join(args)} failed: {json.dumps(data.get('error'))[:1500]}")
    return data


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def main() -> None:
    plan = json.loads((WORLD / "plan.json").read_text())
    requests = [json.loads(line) for line in gzip.open(WORLD / "sessions-requests.jsonl.gz", "rt")]
    agent = kitaru("agent", "register", "helpdesk-agent", "--description", "Larkspur Goods helpdesk assistant: refunds, parcel status, disputes.", "--display-version", RELEASE,
                   "--command", "python -m helpdesk.agent", "--working-dir", f"/app/releases/{RELEASE}", *TOOLS)["item"]
    agent_id, version_id = agent["agent"]["id"], agent["version"]["id"]

    def record(request: dict[str, Any]) -> None:
        env = {**os.environ, "KITARU_AGENT_ID": agent_id, "KITARU_AGENT_VERSION_ID": version_id, "KITARU_SESSION_NAME": request["id"]}
        out = subprocess.run([sys.executable, "-m", "helpdesk.agent", request["prompt"]], cwd=f"/app/releases/{RELEASE}", env=env, capture_output=True, text=True)
        if out.returncode:
            sys.exit(f"recording {request['id']} failed: {out.stderr[-800:]}")

    t0 = time.time()
    with ThreadPoolExecutor(3) as pool:  # three conversations at a time: the order service serves four requests at once
        list(pool.map(record, requests))
    sessions = {s["name"]: s for s in kitaru("session", "list", "--size", "1000")["items"]}
    refused = sum(r["status"] == 429 for r in rows(ORDERS / "state-requests.jsonl"))
    print(f"recorded {len(sessions)} sessions in {time.time() - t0:.0f}s; refunds {len(rows(FINANCE / 'refunds.jsonl'))}, escalations {len(rows(FINANCE / 'escalations.jsonl'))}, lookups refused {refused}", flush=True)
    if len(sessions) != plan["sessions"] or set(sessions) != {r["id"] for r in requests} or refused:
        sys.exit(f"server holds {len(sessions)} sessions, the plan says {plan['sessions']}; {refused} lookups were refused")

    kitaru("evaluator", "register", "refund-once", "--script", "/app/evaluators/refund_once.py", "--entrypoint", "evaluate", "--description", "Passes when a conversation issued at most one refund.")
    subprocess.run(["chown", "-R", "agent:agent", str(APP)], check=True)
    subprocess.run(["runuser", "-u", "agent", "--", "sh", "-c", "cd /app && find . -name __pycache__ -prune -exec rm -rf {} + ; git init -q -b main && git add -A && "
                    "git -c user.name=larkspur -c user.email=dev@larkspur.example commit -q -m 'Helpdesk assistant: release 2.0.0'"], check=True)
    head = subprocess.run(["git", "-c", "safe.directory=/app", "-C", "/app", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    Path("/etc/kitaru-bench/helpdesk.json").write_text(json.dumps({
        "agent_id": agent_id, "versions": {RELEASE: version_id}, "sessions": {name: s["id"] for name, s in sessions.items()},
        "refund_rows": len(rows(FINANCE / "refunds.jsonl")), "escalation_rows": len(rows(FINANCE / "escalations.jsonl")), "head": head}))
    os.chmod("/etc/kitaru-bench/helpdesk.json", 0o600)  # the grader's record of the starting state; root only
    os.chmod(ORDERS, 0o700)


if __name__ == "__main__":
    main()
