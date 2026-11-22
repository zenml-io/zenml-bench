"""Grader for O3. Checks that planner.py and tools.py are untouched and that the finance service received no call from the agent's
work. Serves hidden orders, runs hidden requests through `bin/assistant.sh` as user `grader` (these runs are live and the grader's
own), then replays those conversations and some recorded ones against the newest version of the agent, on its own worker, with a
model-parameter override and a tool policy that answers lookups from the recording and stubs the finance tools. Every replay
must complete, every model call of its result must carry the override, and the replays must pay nobody."""
import json
import os
import subprocess
import sys
from pathlib import Path

from kitaru_checks import SAFE_REPLAY, KitaruError, conversations, finance_rows, kitaru, list_all, repo_changed, serve_orders, start_grader_worker

FIXTURES = Path(__file__).parent / "fixtures"
BEFORE, AGENT = "/etc/kitaru-bench/helpdesk.json", "helpdesk-agent"
OVERRIDE = {"model_params": {"reasoning_effort": "low"}}
DONE = ("completed", "failed", "canceled", "cancelled")


def by_hand(requests: list[dict]) -> dict[str, str]:
    """Run each request through the team's script as user `grader`. Returns request id -> session id for the runs that were recorded."""
    env = {"HOME": "/home/grader", "PATH": os.environ["PATH"], **{k: v for k, v in os.environ.items() if k.startswith("KITARU_") or k == "DO_NOT_TRACK"}}
    for r in requests:
        subprocess.run(["runuser", "-u", "grader", "--", "env", "-i", *(f"{k}={v}" for k, v in env.items()), f"KITARU_SESSION_NAME={r['id']}-by-hand", "bash", "/app/bin/assistant.sh", r["prompt"]],
                       cwd="/app", capture_output=True, text=True, timeout=300)
    names = {f"{r['id']}-by-hand": r["id"] for r in requests}
    return {names[s["name"]]: s["id"] for s in list_all("session", "list", "--origin", "recorded") if s.get("name") in names and s.get("status") == "completed"}


def grade() -> dict:
    import time
    before = json.loads(Path(BEFORE).read_text())
    truth = json.loads((FIXTURES / "ground_truth.json").read_text())["requests"]
    agent = kitaru("agent", "get", AGENT, check=False)
    if not agent.get("ok") or agent["item"]["id"] != before["agent_id"]:
        return {"reward": 0, "reason": f"{AGENT} is not the agent that was registered"}
    newest = sorted(list_all("agent", "version", "list", AGENT), key=lambda v: v["version"])[-1]
    spec = newest.get("run_spec") or {}
    metrics: dict = {"planner_and_tools_untouched": not repo_changed(before["head"], "releases/2.0.0/helpdesk/planner.py", "releases/2.0.0/helpdesk/tools.py"),
                     "newest_version": {"version": newest["version"], "command": spec.get("command"), "working_dir": spec.get("working_dir"), "env": sorted(spec.get("env") or {}), "runtime_capabilities": spec.get("runtime_capabilities")},
                     "new_refunds": finance_rows("refunds") - before["refund_rows"], "new_escalations": finance_rows("escalations") - before["escalation_rows"]}
    start_grader_worker()
    pick = lambda rows, key: [r for kind in ("refund", "status", "dispute") for r in [x for x in rows if x["kind"] == kind and not x["guest"]][:2]]
    hidden = pick(json.loads((FIXTURES / "hidden_requests.json").read_text()), "id")
    serve_orders(str(FIXTURES / "hidden_services_data.json"), "grader-by-hand")
    ran = by_hand(hidden)
    metrics["hidden_requests_run_by_hand"] = f"{len(ran)}/{len(hidden)}"
    paid = finance_rows("refunds"), finance_rows("escalations")
    sessions = list(ran.values()) + [before["sessions"][r["id"]] for r in pick(sorted(truth.values(), key=lambda r: r["id"]), "id")]
    created = {}
    for s in sessions:
        made = kitaru("replay", "create", s, "--evaluator", "refund-once@1", "--agent", f"{AGENT}@{newest['version']}", "--override", json.dumps(OVERRIDE), "--tool-policy", json.dumps(SAFE_REPLAY), check=False)
        created[s] = made["item"]["id"] if made.get("ok") else "refused: " + str((made.get("error") or {}).get("message"))[:120]
    settled: dict[str, dict] = {}
    deadline = time.time() + 420
    while time.time() < deadline and len(settled) < sum(not v.startswith("refused") for v in created.values()):
        for s, replay in created.items():
            if s not in settled and not replay.startswith("refused"):
                item = kitaru("replay", "get", replay)["item"]
                if item["status"] in DONE:
                    settled[s] = item
        time.sleep(2)
    done = [r for r in settled.values() if r["status"] == "completed" and r.get("result_session_id")]
    stored = conversations([r["result_session_id"] for r in done])
    overridden = sum(bool(c["model_params"]) and all((p or {}).get("reasoning_effort") == "low" for p in c["model_params"]) for c in stored.values())
    metrics["replays"] = {"asked": len(sessions), "refused": sorted({v for v in created.values() if v.startswith("refused")}), "completed": len(done), "with_the_override_on_every_model_call": overridden,
                          "errors": sorted({str(r.get("error"))[:160] for r in settled.values() if r["status"] != "completed"})[:4],
                          "refunds_paid_by_the_replays": finance_rows("refunds") - paid[0], "escalations_by_the_replays": finance_rows("escalations") - paid[1]}
    metrics["replays_ok"] = len(ran) == len(hidden) and len(done) == len(sessions) == overridden and not metrics["replays"]["refunds_paid_by_the_replays"] and not metrics["replays"]["escalations_by_the_replays"]
    metrics["reward"] = int(metrics["planner_and_tools_untouched"] and metrics["replays_ok"] and metrics["new_refunds"] == 0 and metrics["new_escalations"] == 0)
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
