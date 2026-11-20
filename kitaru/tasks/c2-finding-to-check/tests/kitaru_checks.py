"""Helpers every Kitaru grader shares. `scripts/sync_checks.sh`-style copying applies: a task's
tests/ directory is all Harbor uploads, so each task carries its own copy of this file. Edit this one
and copy it; never edit a task's copy.

A grader runs as root in the verifier phase, after the agent has finished. Rules it follows:

- Read what Kitaru stored, through the CLI's JSON output. Never read the agent's files for the answer.
- Run the agent's registered work again, on inputs the agent never saw, through a worker the grader
  starts itself as user `grader`. The worker the agent had access to is stopped first: it ran as the
  agent's user, so the agent could have replaced it with anything.
"""
import json
import subprocess
import tempfile
import time
import uuid
from typing import Any


class KitaruError(RuntimeError):
    pass


def kitaru(*args: str, check: bool = True) -> dict[str, Any]:
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout or out.stderr)  # the CLI prints a failure's JSON on stderr
    except json.JSONDecodeError:
        data = {"ok": False, "error": {"message": (out.stdout + out.stderr)[-1000:]}}
    if check and not data.get("ok"):
        raise KitaruError(f"kitaru {' '.join(args)}: {json.dumps(data.get('error'))[:1000]}")
    return data


def list_all(*args: str) -> list[dict[str, Any]]:
    """Every item of a list command, following the page cursor."""
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        page = kitaru(*args, "--size", "1000", *(["--cursor", cursor] if cursor else []))
        items += page["items"]
        cursor = (page.get("page") or {}).get("next_cursor")
        if not cursor:
            return items


def start_grader_worker(name: str | None = None, concurrency: int = 4) -> str:
    """Stop every process the agent's user owns (its worker included), make sure Postgres and the server
    are up, and start a fresh worker as user `grader`. Returns the worker's name once it is live."""
    name = name or f"grader-{uuid.uuid4().hex[:8]}"
    subprocess.run(["/opt/kitaru-bench/stop.sh", "--workers"], capture_output=True)
    subprocess.run(["pkill", "-KILL", "-u", "agent"], capture_output=True)
    for _ in range(40):
        if subprocess.run(["/opt/kitaru-bench/start.sh", "--no-worker"], capture_output=True).returncode == 0:
            break
        time.sleep(2)
    else:
        raise KitaruError("Postgres and the Kitaru server did not come up")
    log = open("/var/log/kitaru-bench/grader-worker.log", "a")
    subprocess.Popen(["runuser", "-u", "grader", "--", "kitaru", "worker", "start", "--name", name, "--concurrency", str(concurrency)],
                     cwd="/home/grader", stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(60):
        if any(w["name"] == name and w["status"] == "live" for w in kitaru("worker", "list", "--size", "100")["items"]):
            return name
        time.sleep(1)
    raise KitaruError("the grader's worker did not register")


def latest_version(kind: str, name: str) -> dict[str, Any] | None:
    """The newest version of a registered evaluator, importer or analyzer, or None if the name is not registered."""
    parent = kitaru(kind, "get", name, check=False)
    if not parent.get("ok"):
        return None
    number = parent["item"]["latest_version"]
    return kitaru(kind, "version", "get", f"{name}@{number}")["item"]


def import_hidden(path: str, agent_ref: str, media_type: str = "application/x-ndjson") -> tuple[str, dict[str, str]]:
    """Import a file the agent never saw through the built-in JSONL importer, under a fresh tag.
    Returns the tag and a map from each session's external id to its Kitaru id."""
    tag = f"grader-{uuid.uuid4().hex[:10]}"
    kitaru("session", "import", path, "--importer", "kitaru/kitaru-jsonl@latest", "--agent", agent_ref, "--media-type", media_type,
           "--tag", tag, "--wait", "--timeout", "600", "--request-timeout", "120")
    return tag, {s["external_id"]: s["id"] for s in list_all("session", "list", "--tag", tag)}


def evaluate_sessions(session_ids: list[str], evaluator_ref: str, batch: int = 100) -> list[str]:
    """Run one evaluator version over the given sessions and wait. Kitaru refuses a request with more
    than 100 session-evaluator pairs, so the ids go in batches. Returns the error message of every
    batch that did not settle cleanly (one crashed evaluation task makes its batch report failure; the
    other sessions in it are still evaluated)."""
    errors = []
    for start in range(0, len(session_ids), batch):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("\n".join(session_ids[start:start + batch]) + "\n")
        run = kitaru("session", "evaluate", "--sessions-file", f.name, "--evaluator", evaluator_ref, "--wait", "--timeout", "700", check=False)
        if not run.get("ok"):
            errors.append(str((run.get("error") or {}).get("message"))[:300])
    return errors


def failed_sessions(session_ids: list[str], evaluator_version_id: str) -> tuple[set[str], set[str]]:
    """Which sessions the given evaluator version failed (any result with passed == False), and which it
    produced no result for at all."""
    failed, silent = set(), set()
    for sid in session_ids:
        rows = [e for e in list_all("evaluation", "list", "--filter", json.dumps({"field": "session_id", "op": "eq", "value": sid}))
                if e.get("evaluator_version_id") == evaluator_version_id]
        if not rows:
            silent.add(sid)
        elif any(e.get("passed") is False for e in rows):
            failed.add(sid)
    return failed, silent
