"""Grader for O2 and O4. Serves hidden orders, runs the parcel chaser's entrypoints on them as user `grader` with no agent, version or
session named in the environment, and reads what Kitaru recorded: one completed session per order under the agent `parcel-chaser`, with its model
calls and its tool calls (names, the order as argument, a result). Then replays some of those sessions against the agent's newest
version on its own worker, every tool answered from the recording: each replay must complete with the same tool calls, and the
order service must receive no request while they run."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from kitaru_checks import KitaruError, kitaru, list_all, read_sessions, serve_orders, start_grader_worker

FIXTURES = Path(__file__).parent / "fixtures"
AGENT = "parcel-chaser"
HISTORY = {"default": {"type": "history", "scope": "baseline", "on_miss": "fail"}}
NIGHTLY = False  # whether the app has a nightly entrypoint that takes a file of order ids
DONE = ("completed", "failed", "canceled", "cancelled")


def run(*command: str) -> str:
    env = {"HOME": "/home/grader", "PATH": os.environ["PATH"], **{k: v for k, v in os.environ.items() if (k.startswith("KITARU_") or k == "DO_NOT_TRACK") and k not in ("KITARU_AGENT_ID", "KITARU_AGENT_VERSION_ID", "KITARU_SESSION_NAME", "KITARU_TASK_ID")}}
    out = subprocess.run(["runuser", "-u", "grader", "--", "env", "-i", *(f"{k}={v}" for k, v in env.items()), sys.executable, "-m", *command], cwd="/app", capture_output=True, text=True, timeout=600)
    return out.stderr[-300:] if out.returncode else ""


def tools(stored: dict) -> list[tuple]:
    nodes = sorted(stored["nodes"], key=lambda n: n.get("started_at") or "")
    return [(n.get("tool_name"), json.dumps(n.get("inputs"), sort_keys=True)) for n in nodes if n["node_type"] == "tool_call"]


def grade() -> dict:
    agent = kitaru("agent", "get", AGENT, check=False)
    if not agent.get("ok"):
        return {"reward": 0, "reason": f"no agent named {AGENT}"}
    agent_id = agent["item"]["id"]
    versions = sorted(list_all("agent", "version", "list", AGENT), key=lambda v: v["version"])
    metrics: dict = {"versions": [{"version": v["version"], "command": (v.get("run_spec") or {}).get("command"), "working_dir": (v.get("run_spec") or {}).get("working_dir")} for v in versions]}
    start_grader_worker()
    data = json.loads((FIXTURES / "hidden_services_data.json").read_text())["orders"]
    orders = sorted(o for o, row in data.items() if row["status"] == "shipped")[:7] + sorted(o for o, row in data.items() if row["status"] != "shipped")[:2]
    by_hand, nightly = (orders[:4], orders[4:]) if NIGHTLY else (orders, [])
    log = serve_orders(str(FIXTURES / "hidden_services_data.json"), "grader-chaser")
    before = {s["id"] for s in list_all("session", "list")}
    errors = [e for e in (run("chaser.agent", o) for o in by_hand) if e]
    if nightly:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("".join(o + "\n" for o in nightly))
        os.chmod(f.name, 0o644)
        errors += [e for e in [run("chaser.nightly", f.name)] if e]
    new = [s for s in list_all("session", "list") if s["id"] not in before]
    stored = {d["session"]["id"]: d for d in read_sessions([s["id"] for s in new])}
    wrong: dict[str, list[str]] = {"not_one_session": [], "not_under_the_agent": [], "not_completed": [], "tool_calls": [], "model_calls": []}
    sessions = {}
    for order in orders:
        mine = [d for d in stored.values() if order in json.dumps(d["session"].get("inputs"))]
        if len(mine) != 1:
            wrong["not_one_session"].append(order)
            continue
        d = mine[0]
        sessions[order] = d["session"]["id"]
        calls = [n for n in d["nodes"] if n["node_type"] == "tool_call"]
        want = ["lookup_order"] + (["get_shipping_status"] if data[order]["status"] == "shipped" else [])
        if d["session"].get("agent_id") != agent_id:
            wrong["not_under_the_agent"].append(order)
        if d["session"].get("status") != "completed" or order not in json.dumps(d["session"].get("outputs")):
            wrong["not_completed"].append(order)
        if (not all(any(n.get("tool_name") == t and order in json.dumps(n.get("inputs")) and n.get("outputs") is not None for n in calls) for t in want)
                or any(n.get("tool_name") not in ("lookup_order", "get_shipping_status") for n in calls)):
            wrong["tool_calls"].append(order)
        if sum(n["node_type"] == "llm_call" for n in d["nodes"]) != len(calls) + 1:
            wrong["model_calls"].append(order)
    metrics["recorded"] = {"orders": len(orders), "new_sessions": len(new), "entrypoint_errors": errors[:3], **{k: len(v) for k, v in wrong.items()}, "examples": {k: v[:4] for k, v in wrong.items() if v}}
    metrics["recorded_ok"] = not errors and not any(wrong.values())
    if not metrics["recorded_ok"] or not versions:
        return metrics | {"reward": 0}

    served = len(open(log).read().splitlines())
    chosen = [sessions[o] for o in (by_hand[:2] + nightly[:2] if NIGHTLY else by_hand[:4])]
    created = {}
    for s in chosen:
        made = kitaru("replay", "create", s, "--evaluator", "refund-once@1", "--agent", f"{AGENT}@{versions[-1]['version']}", "--tool-policy", json.dumps(HISTORY), check=False)
        created[s] = made["item"]["id"] if made.get("ok") else "refused: " + str((made.get("error") or {}).get("message"))[:120]
    settled: dict[str, dict] = {}
    deadline = time.time() + 300
    while time.time() < deadline and len(settled) < sum(not v.startswith("refused") for v in created.values()):
        for s, replay in created.items():
            if s not in settled and not replay.startswith("refused"):
                item = kitaru("replay", "get", replay)["item"]
                if item["status"] in DONE:
                    settled[s] = item
        time.sleep(2)
    done = {s: r for s, r in settled.items() if r["status"] == "completed" and r.get("result_session_id")}
    results = {d["session"]["id"]: d for d in read_sessions([r["result_session_id"] for r in done.values()])}
    same = sum(tools(results[r["result_session_id"]]) == tools(stored[s]) for s, r in done.items())
    metrics["replays"] = {"asked": len(chosen), "refused": sorted({v for v in created.values() if v.startswith("refused")}), "completed": len(done), "with_the_recorded_tool_calls": same,
                          "errors": sorted({str(r.get("error"))[-200:] for r in settled.values() if r["status"] != "completed"})[:3],
                          "requests_to_the_order_service_during_replays": len(open(log).read().splitlines()) - served}
    metrics["replays_ok"] = len(done) == len(chosen) == same and metrics["replays"]["requests_to_the_order_service_during_replays"] == 0
    metrics["reward"] = int(metrics["recorded_ok"] and metrics["replays_ok"])
    return metrics


if __name__ == "__main__":
    try:
        result = grade()
    except KitaruError as e:
        result = {"reward": 0, "reason": f"grader could not finish: {e}"}
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/metrics.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1), file=sys.stderr)
    print(result["reward"])
