"""Grader for I5. Compares what Kitaru holds for August with August's log, then imports a hidden log through the latest
version of `tw-trace` on a worker the grader starts itself and compares again. The importer is the agent's code, so the grader's
files are locked before it runs. The version that was registered before the agent started must still be version 1."""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from kitaru_checks import KitaruError, kitaru, latest_version, list_all, start_grader_worker

FIXTURES = Path(__file__).parent / "fixtures"
IMPORTER, AGENT = "tw-trace", "dispatch-agent"
CALLS = ("llm_call", "tool_call")


def close(a: str | None, b: str | None, seconds: float = 0.001) -> bool:
    if a is None or b is None:
        return a is b
    return abs((datetime.fromisoformat(a.replace("Z", "+00:00")) - datetime.fromisoformat(b.replace("Z", "+00:00"))).total_seconds()) <= seconds


async def read_sessions(ids: list[str]) -> list[dict]:
    from kitaru.client import KitaruAPIClient
    async with KitaruAPIClient() as client:
        gate = asyncio.Semaphore(8)
        async def one(i: str) -> dict:
            async with gate:
                return (await client.sessions.get_with_nodes(i)).model_dump(mode="json")
        return await asyncio.gather(*(one(i) for i in ids))


def wrong_with(stored: dict, want: dict) -> str | None:
    """The first thing about one stored conversation that disagrees with the log, or None."""
    session = stored["session"]
    if session["status"] != want["status"]:
        return f"status {session['status']}, expected {want['status']}"
    if not close(session["started_at"], want["started_at"]) or not close(session["ended_at"], want["ended_at"]):
        return "start or end time"
    if want["message"] not in json.dumps(session.get("inputs"), ensure_ascii=False):
        return "the customer's message is not in the inputs"
    if want["reply"] and want["reply"] not in json.dumps(session.get("outputs"), ensure_ascii=False):
        return "the reply is not in the outputs"
    by_external = {n["external_id"]: n for n in stored["nodes"]}
    calls = [n for n in stored["nodes"] if n["node_type"] in CALLS]
    if len(calls) != len(want["nodes"]):
        return f"{len(calls)} model and tool call nodes, expected {len(want['nodes'])}"
    for node in want["nodes"]:
        match = next((n for n in calls if n["node_type"] == node["type"] and close(n["started_at"], node["started_at"])), None)
        if match is None:
            return f"no {node['type']} node starting at {node['started_at']}"
        if not close(match["ended_at"], node["ended_at"]):
            return "a node's end time"
        parent = by_external.get(match.get("parent_external_id") or "")
        if parent is not None and parent["node_type"] not in CALLS:
            parent = None  # a span above the top-level calls is fine
        if (parent is None) != (node["parent_started_at"] is None) or (parent is not None and not close(parent["started_at"], node["parent_started_at"])):
            return f"the parent of the {node.get('tool_name') or 'model'} call at {node['started_at']}"
        if node["type"] == "llm_call":
            tokens = match.get("tokens") or {}
            if match.get("model") != node["model"] or any((tokens.get(k) or 0) != node[k] for k in ("input_tokens", "output_tokens", "cached_input_tokens")):
                return "a model call's model or token counts"
            if abs(float(match.get("cost") or 0) - node["cost"]) > 1e-6:
                return "a model call's cost"
        elif match.get("tool_name") != node["tool_name"] or match["status"] != node["status"]:
            return "a tool call's name or status"
    if abs(float(session.get("cost") or 0) - want["cost"]) > 1e-6:
        return "the session's total cost"
    return None


def compare(listed: list[dict], want: dict) -> dict:
    by_external: dict[str, list[dict]] = {}
    for s in listed:
        by_external.setdefault(s["external_id"], []).append(s)
    single = [found[0]["id"] for found in by_external.values() if len(found) == 1]
    stored = {r["session"]["external_id"]: r for r in asyncio.run(read_sessions(single))}
    problems = {}
    for conv, expected in want.items():
        found = by_external.get(conv, [])
        if len(found) != 1:
            problems[conv] = f"{len(found)} sessions with this external id"
        elif found[0].get("origin") != "imported" or not found[0].get("import_id") or not found[0].get("task_id"):
            problems[conv] = "not created by an import"
        else:
            problems[conv] = wrong_with(stored[conv], expected)
    problems = {conv: p for conv, p in problems.items() if p}
    return {"conversations_in_log": len(want), "sessions": len(listed), "unexpected_sessions": sum(s["external_id"] not in want for s in listed),
            "conversations_right": len(want) - len(problems), "first_problems": dict(sorted(problems.items())[:6]),
            "cost_in_kitaru": round(sum(float(s.get("cost") or 0) for s in listed), 6), "cost_in_log": round(sum(w["cost"] for w in want.values()), 6)}


def right(c: dict) -> bool:
    return c["conversations_right"] == c["conversations_in_log"] and not c["unexpected_sessions"]


def grade() -> dict:
    before = json.loads(Path("/etc/kitaru-bench/i5.json").read_text())
    start_grader_worker()
    importer = kitaru("importer", "get", IMPORTER, check=False)
    if not importer.get("ok"):
        return {"reward": 0, "reason": f"no importer named {IMPORTER} is registered"}
    first = kitaru("importer", "version", "get", f"{IMPORTER}@1", check=False)
    version = latest_version("importer", IMPORTER)
    agent = kitaru("agent", "get", AGENT, check=False)
    metrics: dict = {"importer_version": version["version"],
                     "old_version_kept": importer["item"]["id"] == before["importer_id"] and bool(first.get("ok")) and first["item"]["id"] == before["version_id"],
                     "agent_ok": bool(agent.get("ok")) and agent["item"]["id"] == before["agent_id"] and agent["item"]["latest_version"] == 1}
    if not metrics["agent_ok"]:
        return metrics | {"reward": 0, "reason": f"{AGENT} is not the agent that was registered, or has a new version"}
    imports = {i["id"]: i for i in list_all("import", "list")}
    versions = {v["id"] for v in list_all("importer", "version", "list", IMPORTER)}
    august = list_all("session", "list", "--agent", AGENT)
    metrics["august"] = compare(august, json.loads((FIXTURES / "month_expected.json").read_text())["sessions"])
    metrics["august_through_tw_trace"] = all((imports.get(s.get("import_id")) or {}).get("importer_version_id") in versions for s in august)
    tag = "grader-hidden-log"
    run = kitaru("session", "import", str(FIXTURES / "hidden.log.jsonl"), "--importer", f"{IMPORTER}@{version['version']}", "--agent", f"{AGENT}@1",
                 "--media-type", "application/x-ndjson", "--tag", tag, "--wait", "--timeout", "600", "--request-timeout", "120", check=False)
    metrics |= {"import_ok": bool(run.get("ok")), "import_error": str((run.get("error") or {}).get("message"))[:300] if not run.get("ok") else None}
    metrics["hidden"] = compare(list_all("session", "list", "--tag", tag), json.loads((FIXTURES / "hidden_expected.json").read_text())["sessions"])
    metrics["reward"] = int(metrics["old_version_kept"] and version["version"] >= 2 and right(metrics["august"]) and metrics["august_through_tw_trace"] and right(metrics["hidden"]))
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
