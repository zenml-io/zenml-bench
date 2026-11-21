"""Helpers every Kitaru grader shares. `scripts/sync_checks.sh`-style copying applies: a task's
tests/ directory is all Harbor uploads, so each task carries its own copy of this file. Edit this one
and copy it; never edit a task's copy.

A grader runs as root in the verifier phase, after the agent has finished. Rules it follows:

- Read what Kitaru stored, through the CLI's JSON output. Never read the agent's files for the answer.
- Run the agent's registered work again, on inputs the agent never saw, through a worker the grader
  starts itself as user `grader`. The worker the agent had access to is stopped first: it ran as the
  agent's user, so the agent could have replaced it with anything.
- Before running any of the agent's code, lock the grader's files (`lock_grader_files`). Code the agent
  registered runs during grading, on the same disk as the answer key.
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


GRADER_ONLY = ["/tests", "/solution", "/logs"]


def lock_grader_files() -> None:
    """Make the grader's own files readable by root only. The grader is about to run code the agent
    registered (an evaluator, an importer) as user `grader`, and the answer key sits in /tests at that
    moment: an evaluator that opened /tests/fixtures/hidden_labels.json scored a perfect 1 before
    this existed (shortcut `read_grader_labels.sh`)."""
    for path in GRADER_ONLY:
        subprocess.run(["chmod", "-R", "go-rwx", path], capture_output=True)


def start_grader_worker(name: str | None = None, concurrency: int = 4) -> str:
    """Stop every process the agent's user owns (its worker included), make sure Postgres and the server
    are up, and start a fresh worker as user `grader`. Returns the worker's name once it is live."""
    name = name or f"grader-{uuid.uuid4().hex[:8]}"
    lock_grader_files()
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


def sessions_by_external_id(tag: str = "history") -> dict[str, str]:
    """Map each session's external id to its Kitaru id, for every session carrying the tag."""
    return {s["external_id"]: s["id"] for s in list_all("session", "list", "--tag", tag)}


def all_evaluations() -> list[dict[str, Any]]:
    """Every stored evaluation row, oldest first."""
    return sorted(list_all("evaluation", "list"), key=lambda e: e["created"])


def grade_evaluator_on_hidden(evaluator: str, hidden_jsonl: str, labels: dict[str, bool], agent_ref: str, min_version: int = 1) -> dict[str, Any]:
    """Run the latest registered version of `evaluator` on hidden sessions and score which ones it
    failed against `labels` (external id -> should this session fail?). Starts the grader's own worker
    first. Returns metrics including `precision` and `recall` over the sessions that should fail."""
    metrics: dict[str, Any] = {}
    start_grader_worker()
    version = latest_version("evaluator", evaluator)
    if version is None:
        return metrics | {"reason": f"no evaluator named {evaluator} is registered"}
    metrics["evaluator_version"] = version["version"]
    if version["version"] < min_version:
        return metrics | {"reason": f"{evaluator} is still at version {version['version']}; no new version was registered"}
    tag, ids = import_hidden(hidden_jsonl, agent_ref)
    if set(ids) != set(labels):
        return metrics | {"reason": f"imported {len(ids)} hidden sessions, expected {len(labels)}"}
    metrics["evaluate_errors"] = evaluate_sessions(list(ids.values()), f"{evaluator}@{version['version']}")
    failed, silent = failed_sessions(list(ids.values()), version["id"])
    should_fail = {ids[x] for x, bad in labels.items() if bad}
    true_pos = len(failed & should_fail)
    by_id = {v: k for k, v in ids.items()}
    return metrics | {"hidden_sessions": len(ids), "should_fail": len(should_fail), "failed_by_evaluator": len(failed), "true_positives": true_pos,
                      "no_result": len(silent), "precision": round(true_pos / len(failed), 4) if failed else 0.0, "recall": round(true_pos / len(should_fail), 4),
                      "false_alarm_ids": sorted(by_id[s] for s in failed - should_fail), "missed_ids": sorted(by_id[s] for s in should_fail - failed)}


def cohort_external_ids(name: str) -> set[str] | None:
    """The external ids of the sessions in the latest version of the cohort `name`. None if no cohort
    has that name; an empty set if it has no version yet."""
    cohort = kitaru("cohort", "get", name, check=False)
    if not cohort.get("ok"):
        return None
    number = cohort["item"]["latest_version"]
    if not number:
        return set()
    version_id = kitaru("cohort", "version", "get", f"{name}@{number}")["item"]["id"]
    return {s["external_id"] for s in list_all("session", "list", "--filter", json.dumps({"field": "cohort_version_id", "op": "eq", "value": version_id}))}


def score_cohort(name: str, truth: set[str], bar: float = 0.9) -> dict[str, Any]:
    """Compare the cohort's members with the sessions that belong in it. `ok` needs precision and
    recall of at least `bar`. A diagnosis task's answer sheet is a cohort: nothing to parse, and
    "find all of them" is graded, not "find one"."""
    members = cohort_external_ids(name)
    if members is None:
        return {"ok": False, "reason": f"no cohort named {name}"}
    hits = len(members & truth)
    precision, recall = (hits / len(members) if members else 0.0), hits / len(truth)
    return {"ok": precision >= bar and recall >= bar, "members": len(members), "belong": len(truth), "hits": hits, "precision": round(precision, 4), "recall": round(recall, 4),
            "wrong_members": sorted(members - truth)[:25], "missed": sorted(truth - members)[:25]}


def read_answer_file(path: str, max_bytes: int = 20_000) -> dict[str, Any] | None:
    """The agent's small answer file, or None if it is missing, a link, too large or not a JSON object.
    The grader runs as root, so a link is refused: it could point at the answer key."""
    import os
    if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) > max_bytes:
        return None
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def ticket_problems(sessions: list[dict[str, Any]], want: dict[str, dict[str, Any]], project: str, version_ids: dict[str, str] | None = None) -> dict[str, str]:
    """For Langfuse exports of a support assistant (world `exports`): what is wrong, per expected ticket, with the sessions
    Kitaru holds. `want` maps a ticket id to its traces in order, call counts, cost and release; a ticket is right when exactly
    one session has the external id `<project>:<ticket>`, was created by an import through the Langfuse importer, holds the
    ticket's traces in order, and (when `version_ids` maps a release to an agent version id) sits under its release's version."""
    by_external: dict[str, list[dict[str, Any]]] = {}
    for s in sessions:
        by_external.setdefault(s.get("external_id") or "", []).append(s)
    problems = {}
    for ticket, w in want.items():
        found = by_external.get(f"{project}:{ticket}", [])
        if len(found) != 1:
            problems[ticket] = f"{len(found)} sessions with external id {project}:{ticket}"
            continue
        s = found[0]
        if s.get("origin") != "imported" or s.get("imported_from") != "langfuse" or not s.get("import_id") or not s.get("task_id"):
            problems[ticket] = "not created by an import through the Langfuse importer"
        elif (s.get("metadata") or {}).get("langfuse.trace_ids") != w["traces"]:
            problems[ticket] = "does not hold the ticket's turns in order"
        elif (s.get("llm_call_count"), s.get("tool_call_count")) != (w["llm_calls"], w["tool_calls"]):
            problems[ticket] = "model or tool call count"
        elif abs(float(s.get("cost") or 0) - w["cost"]) > 1e-6:
            problems[ticket] = "cost"
        elif version_ids is not None and s.get("agent_version_id") != version_ids.get(w["release"]):
            problems[ticket] = f"not under the version for release {w['release']}"
    return problems


def run_agent_script(script: str, *args: str, timeout: int = 900) -> dict[str, Any]:
    """Run a script the agent left in /app, as user `agent` from /app, the way the team's scheduler would. Call
    `start_grader_worker` first: it locks the grader's files and starts the worker that will run the script's jobs."""
    try:
        out = subprocess.run(["runuser", "-u", "agent", "--", "env", "HOME=/home/agent", "bash", script, *args], cwd="/app", capture_output=True, text=True, timeout=timeout)
        return {"exit_code": out.returncode, "output_tail": (out.stdout + out.stderr)[-600:]}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "output_tail": f"did not finish in {timeout} s"}


# ---- world helpdesk-live: an agent that really runs, a finance service that records every refund ----

FINANCE = "/var/lib/helpdesk-finance"
SAFE_REPLAY = {"default": {"type": "history", "scope": "baseline", "on_miss": "fail"},
               "tools": {name: {"type": "static", "on_miss": "fail", "cases": [{"match_mode": "subset", "match": {}, "result": result}]}
                         for name, result in (("issue_refund", {"receipt": "rf_grader_replay", "status": "issued"}), ("escalate_to_human", {"case": "cs_grader_replay", "status": "paged"}))}}


def finance_rows(kind: str) -> int:
    """How many calls of one kind (`refunds`, `escalations`) the finance service has received. The file is root-only."""
    import os
    path = f"{FINANCE}/{kind}.jsonl"
    return len(open(path).read().splitlines()) if os.path.exists(path) else 0


def repo_changed(since: str, *paths: str) -> bool:
    """True when any tracked file under `paths` in /app differs from commit `since`, in the working tree or in a later commit."""
    out = subprocess.run(["git", "-c", "safe.directory=/app", "-C", "/app", "diff", "--quiet", since, "--", *paths], capture_output=True)
    return out.returncode != 0


def record_requests(requests: list[dict[str, Any]], release_dir: str, agent_id: str, version_id: str) -> dict[str, str]:
    """Run the assistant in `release_dir` once per request, as user `grader`, so each becomes a recorded session under
    the given agent version. These runs are live: the finance service receives their refunds. Returns request id -> session id."""
    import os
    for r in requests:
        env = {"KITARU_AGENT_ID": agent_id, "KITARU_AGENT_VERSION_ID": version_id, "KITARU_SESSION_NAME": r["id"], "HOME": "/home/grader", "PATH": os.environ["PATH"],
               **{k: v for k, v in os.environ.items() if k.startswith("KITARU_") or k == "DO_NOT_TRACK"}}
        env |= {"KITARU_AGENT_ID": agent_id, "KITARU_AGENT_VERSION_ID": version_id, "KITARU_SESSION_NAME": r["id"]}
        out = subprocess.run(["runuser", "-u", "grader", "--", "env", "-i", *(f"{k}={v}" for k, v in env.items()), sys_python(), "-m", "helpdesk.agent", r["prompt"]],
                             cwd=release_dir, capture_output=True, text=True)
        if out.returncode:
            raise KitaruError(f"recording {r['id']} failed: {out.stderr[-400:]}")
    wanted = {r["id"] for r in requests}
    return {s["name"]: s["id"] for s in list_all("session", "list", "--origin", "recorded") if s.get("name") in wanted}


def sys_python() -> str:
    import sys
    return sys.executable


def replay_sessions(session_ids: list[str], agent_ref: str, evaluator_ref: str, policy: dict[str, Any] = SAFE_REPLAY, timeout: int = 900) -> dict[str, dict[str, Any]]:
    """Replay each session against `agent_ref` and wait. Returns baseline session id -> the settled replay."""
    created = {s: kitaru("replay", "create", s, "--evaluator", evaluator_ref, "--agent", agent_ref, "--tool-policy", json.dumps(policy))["item"]["id"] for s in session_ids}
    done: dict[str, dict[str, Any]] = {}
    deadline = time.time() + timeout
    while len(done) < len(created) and time.time() < deadline:
        for s, replay in created.items():
            if s not in done:
                item = kitaru("replay", "get", replay)["item"]
                if item["status"] in ("completed", "failed", "cancelled", "canceled"):
                    done[s] = item
        time.sleep(1)
    return {s: done.get(s) or {"status": "timeout", "result_session_id": None} for s in created}


def verdict(session_id: str, evaluator_version_id: str) -> bool | None:
    """The newest verdict one evaluator version gave a session; None if it gave none."""
    rows = [e for e in list_all("evaluation", "list", "--filter", json.dumps({"field": "session_id", "op": "eq", "value": session_id})) if e.get("evaluator_version_id") == evaluator_version_id]
    return max(rows, key=lambda e: e["created"]).get("passed") if rows else None


ORDERS = "/var/lib/helpdesk-orders"


def serve_orders(data_path: str, tag: str) -> str:
    """World `helpdesk-services`: stop the order service and start it on other orders with an empty memory.
    Returns the path of its request log, one JSON line per request with the HTTP status it answered."""
    import os
    import urllib.request
    subprocess.run(["pkill", "-f", "/opt/helpdesk/order_service.py"], capture_output=True)
    time.sleep(0.5)
    state, log = f"{ORDERS}/{tag}.json", f"{ORDERS}/{tag}-requests.jsonl"
    for path in (state, log):
        if os.path.exists(path):
            os.remove(path)
    out = open("/var/log/kitaru-bench/orders.log", "a")
    subprocess.Popen([sys_python(), "/opt/helpdesk/order_service.py", "--data", data_path, "--state", state], cwd="/", stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(40):
        try:
            urllib.request.urlopen("http://127.0.0.1:8092/health", timeout=2).read()
            return log
        except OSError:
            time.sleep(0.5)
    raise KitaruError("the order service did not start")


def run_assistant(requests: list[dict[str, Any]], release_dir: str, agent_id: str, version_id: str, tag: str, workers: int = 1) -> dict[str, str]:
    """Run the assistant in `release_dir` once per request, as user `grader`, `workers` conversations at a time. Each run is
    live (the services receive its calls) and is recorded as the session `<request id>-<tag>`. Returns request id -> session id,
    plus `failed:<request id>` -> why, for each run that exited with an error, could not start (a release directory that does
    not exist) or did not finish in 300 seconds. After one run hangs, the rest are not started: a release that hangs once
    would otherwise use up the verifier's whole time limit."""
    import os
    from concurrent.futures import ThreadPoolExecutor

    hung: list[str] = []

    def one(r: dict[str, Any]) -> str | None:
        if hung:
            return f"not started: the conversation for {hung[0]} did not finish in 300 seconds"
        env = {"HOME": "/home/grader", "PATH": os.environ["PATH"], **{k: v for k, v in os.environ.items() if k.startswith("KITARU_") or k == "DO_NOT_TRACK"},
               "KITARU_AGENT_ID": agent_id, "KITARU_AGENT_VERSION_ID": version_id, "KITARU_SESSION_NAME": f"{r['id']}-{tag}"}
        try:
            out = subprocess.run(["runuser", "-u", "grader", "--", "env", "-i", *(f"{k}={v}" for k, v in env.items()), sys_python(), "-m", "helpdesk.agent", r["prompt"]],
                                 cwd=release_dir, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            hung.append(r["id"])
            return "did not finish in 300 seconds"
        except OSError as e:
            return f"could not start: {e}"
        return (out.stderr[-300:] or f"exit code {out.returncode}") if out.returncode else None

    with ThreadPoolExecutor(workers) as pool:
        failed = {r["id"]: e for r, e in zip(requests, pool.map(one, requests)) if e}
    names = {f"{r['id']}-{tag}": r["id"] for r in requests}
    found = {names[s["name"]]: s["id"] for s in list_all("session", "list", "--origin", "recorded") if s.get("name") in names}
    return found | {f"failed:{i}": e for i, e in failed.items()}


def read_sessions(session_ids: list[str]) -> list[dict[str, Any]]:
    """Sessions with their nodes as Kitaru stores them ({"session": ..., "nodes": [...]}), in the order asked for. Read through
    the Python client: the CLI's node list leaves the arguments and results out."""
    import asyncio

    from kitaru.client import KitaruAPIClient

    async def fetch() -> list[dict[str, Any]]:
        async with KitaruAPIClient() as client:
            gate = asyncio.Semaphore(8)

            async def one(i: str) -> dict[str, Any]:
                async with gate:
                    return (await client.sessions.get_with_nodes(i)).model_dump(mode="json")
            return await asyncio.gather(*(one(i) for i in session_ids))

    return asyncio.run(fetch())


def conversations(session_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Recorded conversations as a grader compares them, by session id: the tool calls in order (name, arguments, result, start
    and end in seconds), the assistant's last message with receipt and case numbers blanked, since those differ on every run,
    and the model parameters of each model call."""
    import re
    from datetime import datetime

    stamp = lambda t: datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp() if t else None
    out = {}
    for session_id, stored in zip(session_ids, read_sessions(session_ids)):
        nodes = sorted(stored["nodes"], key=lambda n: n.get("started_at") or "")
        calls = [{"tool": n.get("tool_name"), "inputs": n.get("inputs"), "outputs": n.get("outputs"), "start": stamp(n.get("started_at")), "end": stamp(n.get("ended_at"))}
                 for n in nodes if n["node_type"] == "tool_call"]
        texts = [p.get("content") for n in nodes if n["node_type"] == "llm_call" for p in ((n.get("outputs") or {}).get("parts") or []) if p.get("part_kind") == "text"]
        out[session_id] = {"calls": calls, "answer": re.sub(r"\b(rf|cs)_\w+", r"\1_#", texts[-1]) if texts else None,
                           "model_params": [n.get("model_params") for n in nodes if n["node_type"] == "llm_call"]}
    return out
