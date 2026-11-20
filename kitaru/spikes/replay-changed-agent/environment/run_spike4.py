"""Changed-agent replay spike. Version 1 of the agent refunds euro orders 100 times too much; version 2
has the fix. Record 12 sessions with version 1, then replay them against both versions under three
tool policies, alone and as experiments over a cohort, and report what Kitaru stored each time.

    python run_spike4.py --out /app/spike4.json
"""
import argparse
import json
import os
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

LEDGER = Path("/app/ledger.jsonl")
FIX_FLAG = Path("/app/fix_enabled")
RUN = ["--command", "python -m spike_agent.agent", "--working-dir", "/app", "--tool", "lookup_order", "--tool", "issue_refund"]
HISTORY_FAIL = {"type": "history", "scope": "baseline", "on_miss": "fail"}
POLICIES = {
    "history_fail": {"default": HISTORY_FAIL},
    "history_error_result": {"default": {"type": "history", "scope": "baseline", "on_miss": "error_result"}},
    "refund_static": {"default": HISTORY_FAIL, "tools": {"issue_refund": {
        "type": "static", "on_miss": "fail", "cases": [{"match_mode": "subset", "match": {}, "result": {"receipt": "not-sent-replay"}}]}}},
}


def kitaru(*args: str, check: bool = True) -> dict[str, Any]:
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        data = {"ok": False, "error": {"message": (out.stdout + out.stderr)[-600:]}}
    if check and not data.get("ok"):
        raise RuntimeError(f"kitaru {' '.join(args)} failed: {json.dumps(data.get('error'))[:900]}")
    return data


def ledger_rows() -> int:
    return len(LEDGER.read_text().splitlines()) if LEDGER.exists() else 0


def answer(session_id: str) -> str | None:
    nodes = kitaru("session", "nodes", session_id, "--include-payloads", "--size", "100")["items"]
    return next((n["outputs"] for n in nodes if n["external_id"] == "root"), None)


def verdict(session_id: str) -> bool | None:
    rows = kitaru("evaluation", "list", "--filter", json.dumps({"field": "session_id", "op": "eq", "value": session_id}), "--size", "20")["items"]
    return rows[0]["passed"] if rows else None


def task_error(job_id: str) -> str | None:
    tasks = kitaru("job", "get", job_id, "--tasks", check=False).get("item", {}).get("tasks", [])
    return next((str(t["error"]).strip().splitlines()[-1][-300:] for t in tasks if t.get("error")), None)


def replay_all(sessions: dict[str, str], agent_ref: str, policy: str) -> dict[str, Any]:
    """Replay every session once and summarise: statuses, verdicts, which answers changed, ledger rows added."""
    before, t0 = ledger_rows(), time.time()
    replays = {name: kitaru("replay", "create", sid, "--evaluator", "refund-amount@1", "--agent", agent_ref,
                            "--tool-policy", json.dumps(POLICIES[policy]))["item"] for name, sid in sessions.items()}
    deadline, done = time.time() + 600, {}
    while len(done) < len(replays) and time.time() < deadline:
        for name, r in replays.items():
            if name not in done:
                item = kitaru("replay", "get", r["id"])["item"]
                if item["status"] in ("completed", "failed", "cancelled"):
                    done[name] = item
        time.sleep(1)
    per_session = {}
    for name, item in done.items():
        sid = item.get("result_session_id")
        per_session[name] = {"status": item["status"], "passed": verdict(sid) if sid else None, "answer": answer(sid) if sid else None,
                             "error": item.get("error") or (task_error(item["job_id"]) if item["status"] == "failed" else None)}
    return {"agent": agent_ref, "policy": policy, "statuses": dict(Counter(p["status"] for p in per_session.values())),
            "verdicts": dict(Counter(str(p["passed"]) for p in per_session.values())), "ledger_rows_added": ledger_rows() - before,
            "seconds": round(time.time() - t0, 1), "per_session": per_session}


def run_experiment(name: str, policy: str, cohort_version: str, agent_ref: str) -> dict[str, Any]:
    before = ledger_rows()
    kitaru("experiment", "create", name, "--agent", "spike-agent", "--evaluator", "refund-amount@1", "--tool-policy", json.dumps(POLICIES[policy]))
    start = kitaru("experiment", "run", "start", name, "--cohort-version", cohort_version, "--agent", agent_ref, "--wait", "--timeout", "600", check=False)
    # A run that settles as failed makes the CLI exit with an error; its id is then only in the error text.
    found = re.search(r"experiment run get ([0-9a-f-]{36})", json.dumps(start))
    run = kitaru("experiment", "run", "get", found.group(1), check=False).get("item") if found else None
    return {"policy": policy, "agent": agent_ref, "cli_ok": bool(start.get("ok")), "status": (run or {}).get("status"),
            "progress": (run or {}).get("progress"), "ledger_rows_added": ledger_rows() - before}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/app/spike4.json"))
    a = ap.parse_args()
    agent = kitaru("agent", "register", "spike-agent", *RUN)["item"]["agent"]["id"]
    v2 = kitaru("agent", "version", "register", "spike-agent", *RUN, "--env", "SPIKE_FIX=1")["item"]
    kitaru("evaluator", "register", "refund-amount", "--script", "/app/refund_amount_evaluator.py", "--entrypoint", "evaluate")
    for i in range(1, 13):
        subprocess.run(["python", "-m", "spike_agent.agent", f"Refund order A-{i}"], check=True, capture_output=True, env={**os.environ, "KITARU_AGENT_ID": agent}, cwd="/app")
    sessions = {s["name"]: s["id"] for s in kitaru("session", "list", "--origin", "recorded", "--size", "100")["items"]}
    report: dict[str, Any] = {"version_2": {k: v2.get(k) for k in ("version", "run_spec")} if "version" in v2 else v2,
                              "recorded": {name: answer(sid) for name, sid in sorted(sessions.items(), key=lambda kv: int(kv[0].split("-")[1]))},
                              "ledger_rows_after_recording": ledger_rows()}
    report["replays"] = [replay_all(sessions, ref, pol) for ref, pol in
                         (("spike-agent@1", "history_fail"), ("spike-agent@2", "history_fail"), ("spike-agent@2", "history_error_result"), ("spike-agent@2", "refund_static"))]

    # Is version 1 tied to the code it was registered with? Turn the fix on by "editing the code on disk"
    # (the flag file), then replay one euro session against version 1.
    FIX_FLAG.touch()
    report["version_1_after_code_edit"] = replay_all({"Refund order A-3": sessions["Refund order A-3"]}, "spike-agent@1", "refund_static")
    FIX_FLAG.unlink()

    Path("/app/ids.txt").write_text("\n".join(sessions.values()) + "\n")
    cohort = kitaru("cohort", "create", "recorded-12", "--agent", "spike-agent", "--sessions-file", "/app/ids.txt")["item"]
    cohort_version = (cohort.get("version") or cohort.get("cohort_version") or {}).get("id")
    report["cohort"] = {"keys": sorted(cohort), "version_id": cohort_version}
    report["experiments"] = [run_experiment("fix-history-fail", "history_fail", cohort_version, "spike-agent@2"),
                             run_experiment("fix-refund-static", "refund_static", cohort_version, "spike-agent@2")]
    a.out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
