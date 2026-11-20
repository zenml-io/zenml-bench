"""Spike 2 driver: with the network sealed, run two built-in evaluators, the JSONL importer and the
built-in analyzer. Each is a pinned package the worker installs when the job runs.

    python run_spike2.py --out /app/spike2.json
"""
import argparse
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any


def kitaru(*args: str, check: bool = True) -> dict[str, Any]:
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        data = {"ok": False, "error": {"message": (out.stdout + out.stderr)[-800:]}}
    if check and not data.get("ok"):
        raise RuntimeError(f"kitaru {' '.join(args)} failed: {json.dumps(data.get('error'))[:800]}")
    return data


def task_errors(job_id: str) -> list[str]:
    job = kitaru("job", "get", job_id, "--tasks", check=False).get("item", {})
    return [f"{t['kind']}: {str(t.get('error'))[:600]}" for t in job.get("tasks", []) if t.get("error")]


def pypi_reachable() -> bool:
    try:
        urllib.request.urlopen("https://pypi.org/simple/kitaru-evaluator/", timeout=8)
        return True
    except Exception:
        return False


def jsonl_record(i: int) -> dict[str, Any]:
    return {"status": "completed", "name": f"Weather request {i}", "inputs": {"question": "What is the weather in Delft?"},
            "outputs": {"answer": "Delft is rainy and 18 C."}, "started_at": f"2026-07-22T10:0{i}:00Z", "ended_at": f"2026-07-22T10:0{i}:01Z",
            "external_id": f"weather-session-{i}", "metadata": {"environment": "production"}, "framework": "pydantic-ai",
            "nodes": [{"index": 0, "parent_index": None, "links": [], "external_id": f"model-call-{i}", "trace_id": f"trace-{i}",
                       "node_type": "llm_call", "name": "answer weather question", "status": "completed",
                       "started_at": f"2026-07-22T10:0{i}:00Z", "ended_at": f"2026-07-22T10:0{i}:01Z",
                       "input_text_selector": "/1/content", "output_text_selector": "/0/content", "system_prompt_selector": "/0/content",
                       "reasoning_selectors": [], "inputs": [{"role": "system", "content": "Answer in one sentence."}, {"role": "user", "content": "What is the weather in Delft?"}],
                       "outputs": [{"role": "assistant", "content": "Delft is rainy and 18 C."}], "model": "claude-haiku-4-5-20251001",
                       "model_provider": "anthropic", "tokens": {"input_tokens": 24, "output_tokens": 11, "cached_input_tokens": 0, "cache_write_input_tokens": 0, "reasoning_tokens": 0},
                       "attributes": {}, "metadata": {}}]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/app/spike2.json"))
    a = ap.parse_args()
    report: dict[str, Any] = {"pypi_reachable": pypi_reachable(), "uv_config": Path("/etc/uv/uv.toml").read_text()}

    agent = kitaru("agent", "register", "spike-agent", "--command", "python -m spike_agent.agent", "--working-dir", "/app")["item"]["agent"]["id"]
    for i in (1, 4, 5):
        subprocess.run(["python", "-m", "spike_agent.agent", f"Refund order A-{i}"], check=True, capture_output=True, env={**os.environ, "KITARU_AGENT_ID": agent}, cwd="/app")

    t0 = time.time()
    ev = kitaru("session", "evaluate", "--all", "--evaluator", "kitaru/tool-call-patterns@1", "--evaluator", "kitaru/session-diagnostics@1", "--wait", "--timeout", "300", check=False)
    rows = kitaru("evaluation", "list", "--size", "100", check=False).get("items", [])
    job_id = (ev.get("item") or ev.get("error", {}).get("details", {}).get("receipt", {})).get("job", {}).get("id")
    report["evaluate"] = {"ok": bool(ev.get("ok")), "seconds": round(time.time() - t0, 1), "evaluations": len(rows),
                          "with_evaluator_version_and_task": sum(1 for e in rows if e.get("evaluator_version_id") and e.get("task_id")),
                          "names": sorted({e["name"] for e in rows})[:12], "errors": task_errors(job_id)[:2] if job_id and not ev.get("ok") else []}

    Path("/app/sessions.jsonl").write_text("".join(json.dumps(jsonl_record(i)) + "\n" for i in range(1, 7)))
    t0 = time.time()
    im = kitaru("session", "import", "/app/sessions.jsonl", "--importer", "kitaru/kitaru-jsonl@latest", "--agent", "spike-agent@1",
                "--media-type", "application/x-ndjson", "--analyzer", "kitaru/post-import-insights@1", "--wait", "--timeout", "300", check=False)
    imported = kitaru("session", "list", "--origin", "imported", "--size", "50", check=False).get("items", [])
    insights = kitaru("insight", "list", "--size", "50", check=False)
    report["import"] = {"ok": len(imported) == 6 and all(s.get("import_id") and s.get("task_id") for s in imported), "command_ok": bool(im.get("ok")),
                        "seconds": round(time.time() - t0, 1), "imported_sessions": len(imported),
                        "with_import_id_and_task_id": sum(1 for s in imported if s.get("import_id") and s.get("task_id")),
                        "error": json.dumps(im.get("error"))[:1200] if not im.get("ok") else None}
    report["analyzer"] = {"insights": insights.get("count"), "with_analyzer_version": sum(1 for i in insights.get("items", []) if i.get("analyzer_version_id")),
                          "error": json.dumps(insights.get("error"))[:300] if not insights.get("ok") else None}
    a.out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
