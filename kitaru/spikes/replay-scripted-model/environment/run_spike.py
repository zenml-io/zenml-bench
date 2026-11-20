"""Spike 3 driver: record N sessions with the scripted model, replay each one ROUNDS times with the
recorded-results tool policy, and report whether every replay matches its recording.

    python run_spike.py [--n 20] [--rounds 5] --out /app/spike3.json
"""
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

HISTORY = json.dumps({"default": {"type": "history", "scope": "baseline", "on_miss": "fail"}})
LEDGER = Path(os.environ.get("SPIKE_LEDGER", "/app/ledger.jsonl"))


def kitaru(*args: str) -> dict[str, Any]:
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"kitaru {' '.join(args)} failed: {out.stdout[-500:]} {out.stderr[-500:]}")
    return json.loads(out.stdout)


def ledger_rows() -> int:
    return len(LEDGER.read_text().splitlines()) if LEDGER.exists() else 0


def signature(session_id: str) -> dict[str, Any]:
    """What the session did, without ids and timestamps: the final answer, every tool call with its
    arguments and result, and every model reply."""
    nodes = kitaru("session", "nodes", session_id, "--include-payloads", "--size", "100")["items"]
    steps: list[Any] = []
    answer = None
    for n in nodes:
        if n["node_type"] == "span" and n["external_id"] == "root":
            answer = n["outputs"]
        elif n["node_type"] == "tool_call":
            steps.append(["tool", n["name"], n["inputs"], n["outputs"], n["status"]])
        elif n["node_type"] == "llm_call":
            parts = [[p.get("part_kind"), p.get("tool_name"), p.get("args"), p.get("content")] for p in n["outputs"]["parts"]]
            steps.append(["model", parts, n["tokens"]])
    digest = hashlib.sha256(json.dumps([answer, steps], sort_keys=True).encode()).hexdigest()[:16]
    return {"answer": answer, "n_steps": len(steps), "digest": digest}


def wait_replays(ids: list[str], timeout: float = 600.0) -> dict[str, dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    deadline = time.time() + timeout
    while len(done) < len(ids) and time.time() < deadline:
        for rid in ids:
            if rid not in done:
                item = kitaru("replay", "get", rid)["item"]
                if item["status"] in ("completed", "failed", "cancelled"):
                    done[rid] = item
        time.sleep(1)
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--out", type=Path, default=Path("/app/spike3.json"))
    a = ap.parse_args()

    agent = kitaru("agent", "register", "spike-agent", "--command", "python -m spike_agent.agent", "--working-dir", "/app",
                   "--tool", "lookup_order", "--tool", "issue_refund")["item"]["agent"]["id"]
    kitaru("evaluator", "register", "refund-count", "--script", "/app/refund_count_evaluator.py", "--entrypoint", "evaluate")

    t0 = time.time()
    for i in range(1, a.n + 1):
        subprocess.run(["python", "-m", "spike_agent.agent", f"Refund order A-{i}"], check=True, capture_output=True,
                       env={**os.environ, "KITARU_AGENT_ID": agent}, cwd="/app")
    record_s = time.time() - t0
    sessions = {s["name"]: s["id"] for s in kitaru("session", "list", "--origin", "recorded", "--size", "100")["items"]}
    baseline = {name: signature(sid) for name, sid in sessions.items()}
    rows_after_recording = ledger_rows()

    rounds: list[dict[str, Any]] = []
    for r in range(a.rounds):
        t0 = time.time()
        replay_of = {kitaru("replay", "create", sid, "--evaluator", "refund-count@1", "--agent", "spike-agent@1",
                            "--tool-policy", HISTORY)["item"]["id"]: name for name, sid in sessions.items()}
        done = wait_replays(list(replay_of))
        statuses = [d["status"] for d in done.values()]
        mismatches = [replay_of[rid] for rid, d in done.items()
                      if d["status"] != "completed" or signature(d["result_session_id"])["digest"] != baseline[replay_of[rid]]["digest"]]
        rounds.append({"round": r + 1, "replays": len(replay_of), "completed": statuses.count("completed"), "failed": statuses.count("failed"),
                       "unfinished": len(replay_of) - len(done), "mismatches": mismatches, "seconds": round(time.time() - t0, 1),
                       "ledger_rows": ledger_rows(), "errors": [d["error"] for d in done.values() if d["error"]][:3]})

    # Control: the same replay with no tool policy. Kitaru's default runs the live tools, so this one
    # should add a ledger row and produce a different answer. If it does not, the comparison above proves nothing.
    name, sid = next((n, s) for n, s in sessions.items() if "Refunded" in str(baseline[n]["answer"]))
    rows_before_control = ledger_rows()
    rid = kitaru("replay", "create", sid, "--evaluator", "refund-count@1", "--agent", "spike-agent@1")["item"]["id"]
    control = wait_replays([rid])[rid]
    control_sig = signature(control["result_session_id"]) if control.get("result_session_id") else None
    evaluations = kitaru("evaluation", "list", "--size", "5")
    report = {"sessions_recorded": len(sessions), "record_seconds": round(record_s, 1), "ledger_rows_after_recording": rows_after_recording,
              "baseline_answers_sample": [baseline[n]["answer"] for n in list(baseline)[:3]],
              "baseline_step_counts": sorted({b["n_steps"] for b in baseline.values()}), "rounds": rounds,
              "control_default_policy": {"session": name, "status": control["status"], "ledger_rows_added": ledger_rows() - rows_before_control,
                                         "same_as_recording": control_sig["digest"] == baseline[name]["digest"] if control_sig else None,
                                         "answer": control_sig["answer"] if control_sig else None, "recorded_answer": baseline[name]["answer"]},
              "evaluation_sample": [{k: e.get(k) for k in ("name", "passed", "evaluator_version_id", "task_id")} for e in evaluations.get("items", [])[:2]]}
    report["all_identical"] = all(r["completed"] == r["replays"] and not r["mismatches"] for r in rounds) and rounds[-1]["ledger_rows"] == rows_after_recording
    a.out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
