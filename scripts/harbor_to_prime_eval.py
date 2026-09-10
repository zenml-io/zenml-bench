# /// script
# requires-python = ">=3.14"
# ///
"""Convert Harbor job dirs into the `metadata.json` + `results.jsonl` layout `prime eval push` accepts.

    uv run scripts/harbor_to_prime_eval.py jobs/<job> [jobs/<job2> ...] --out results/prime-evals/<name>/ [--transcripts]
    uv run scripts/harbor_to_prime_eval.py --from-traces outputs/<run> --out results/prime-evals/<name>/   # a verifiers v1 run dir

One results.jsonl row per trial (reward, extra verifier metrics, tokens, cost, timing, task name); metadata.json
carries the model, harness, aggregate rewards and a `note` saying these rows were run through Harbor and converted,
not produced by verifiers' own eval runner. Every job passed in must share one model and one harness (one eval on
the Prime Evals hub is one model on one environment). Transcripts are opt-in (`--transcripts`): they put the agent's
ATIF trajectory (`agent/trajectory.json`) into `completion` as chat messages, which is what the hub viewer shows; read
one before pushing. Nothing here uploads; the push command is printed at the end for Alex to run.

Schema source: verifiers' legacy writer (`verifiers/legacy/utils/save_utils.py`, `GenerateMetadata`/`RolloutOutput`)
and the reader in `prime_cli/commands/evals.py::_load_eval_directory` (needs `env_id`+`model` in metadata; `avg_*`
keys become the eval's metrics; each row needs `example_id` (or `id`) and `reward`; other keys pass through).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HARBOR_VERSION = "0.22.0"
ENV_ID = "zenml/zenml-bench"


def parse_ts(s: str | None) -> float | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() if s else None


def span(block: dict[str, Any] | None) -> dict[str, float] | None:
    if not block or not block.get("started_at"):
        return None
    start, end = parse_ts(block["started_at"]), parse_ts(block.get("finished_at"))
    return {"start": start, "end": end, "seconds": (end - start) if end else None}


def trial_dirs(job: Path) -> list[Path]:
    return sorted(p.parent for p in job.glob("*/result.json"))


def atif_messages(trajectory: Path) -> list[dict[str, Any]]:
    """ATIF steps -> chat messages: system/user text, assistant text + tool calls, tool results."""
    if not trajectory.is_file():
        return []
    steps = json.loads(trajectory.read_text()).get("steps") or []
    out: list[dict[str, Any]] = []
    for step in steps:
        source, text = step.get("source"), step.get("message") or ""
        if source in ("system", "user"):
            out.append({"role": source, "content": text})
            continue
        msg: dict[str, Any] = {"role": "assistant", "content": text}
        if calls := step.get("tool_calls"):
            msg["tool_calls"] = [
                {"id": c.get("tool_call_id"), "type": "function",
                 "function": {"name": c.get("function_name"), "arguments": json.dumps(c.get("arguments", {}))}}
                for c in calls
            ]
        out.append(msg)
        for r in (step.get("observation") or {}).get("results") or []:
            out.append({"role": "tool", "tool_call_id": r.get("source_call_id"), "content": str(r.get("content", ""))})
    return out


def trial_row(trial: Path, transcripts: bool, task_dir_root: Path | None) -> dict[str, Any]:
    result = json.loads((trial / "result.json").read_text())
    rewards = dict((result.get("verifier_result") or {}).get("rewards") or {})
    reward = rewards.pop("reward", None)
    agent_result = result.get("agent_result") or {}
    exc = result.get("exception_info")
    task_name = result.get("task_name") or ""
    short = task_name.split("/", 1)[-1]
    timing = {k: span(result.get(k)) for k in ("environment_setup", "agent_setup", "agent_execution", "verifier")}
    timing["total"] = span({"started_at": result.get("started_at"), "finished_at": result.get("finished_at")})
    row: dict[str, Any] = {
        "example_id": short,  # replaced by an integer index in convert(); kept here for grouping
        "task": task_name,
        "trial": trial.name,
        "job": trial.parent.name,
        "reward": float(reward) if reward is not None else 0.0,
        "metrics": {k: v for k, v in rewards.items() if isinstance(v, (int, float))},
        "is_completed": reward is not None,
        "is_truncated": False,
        "error": {"type": exc.get("exception_type"), "message": exc.get("exception_message")} if exc else None,
        "timing": timing,
        "token_usage": {
            "input_tokens": agent_result.get("n_input_tokens"),
            "output_tokens": agent_result.get("n_output_tokens"),
            "cached_tokens": agent_result.get("n_cache_tokens"),
        },
        "cost_usd": agent_result.get("cost_usd"),
        "prompt": [],
        "completion": [],
    }
    row.update(row["metrics"])  # flattened, as verifiers' writer does
    instruction = task_dir_root / short / "instruction.md" if task_dir_root else None
    if instruction and instruction.is_file():
        row["prompt"] = [{"role": "user", "content": instruction.read_text()}]
    if transcripts:
        row["completion"] = atif_messages(trial / "agent" / "trajectory.json")
    return row


def traces_rows(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A verifiers v1 run dir (`traces.jsonl` episodes + `configs/resolved/eval.json`) -> rows and run facts."""
    cfg = json.loads((run_dir / "configs" / "resolved" / "eval.json").read_text())
    agent_cfg = cfg["env"].get("agent") or {}
    harness = (agent_cfg.get("harness") or {}).get("id") or "bash"
    rows: list[dict[str, Any]] = []
    for line in (run_dir / "traces.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        ep = json.loads(line)
        for tr in ep.get("traces") or []:
            data = tr["task"]["data"]
            # verifiers' trace.reward is the weighted sum of every named reward. A Harbor task that writes
            # reward.json {"reward": x} lands under the key "reward"; one that writes reward.txt lands under the
            # reward function's name ("solved"). Both count.
            rewards = {k: v.get("score") for k, v in (tr.get("rewards") or {}).items() if v}
            total = sum((v.get("score") or 0.0) * (v.get("weight") if v.get("weight") is not None else 1.0)
                        for v in (tr.get("rewards") or {}).values() if v)
            metrics = {k: v for k, v in (tr.get("metrics") or {}).items() if isinstance(v, (int, float))}
            timing = tr.get("timing") or {}
            errors = ep.get("errors") or tr.get("errors") or []
            rows.append({
                "example_id": data.get("idx"),
                "task": data.get("name"),
                "trial": tr.get("id"),
                "job": run_dir.name,
                "reward": float(total),
                "rewards": rewards,
                "metrics": metrics,
                "is_completed": bool(tr.get("is_completed")),
                "is_truncated": bool(tr.get("is_truncated")),
                "error": {"message": str(errors[0])[:2000]} if errors else None,
                "stop_condition": tr.get("stop_condition"),
                "timing": {
                    "total": {"start": timing.get("start"), "end": (timing.get("scoring") or {}).get("end"),
                              "seconds": ((timing.get("scoring") or {}).get("end") or 0) - (timing.get("start") or 0)},
                    "agent": timing.get("agent"), "setup": timing.get("setup"), "scoring": timing.get("scoring"),
                },
                "token_usage": {  # summed over the interception server's per-call usage records
                    "input_tokens": sum((c.get("usage") or {}).get("prompt_tokens") or 0 for c in tr.get("calls") or []),
                    "output_tokens": sum((c.get("usage") or {}).get("completion_tokens") or 0 for c in tr.get("calls") or []),
                    "model_calls": len(tr.get("calls") or []),
                },
                "cost_usd": None,
                "prompt": [{"role": "user", "content": data.get("prompt", "")}],
                "completion": [],
                **metrics,
            })
    facts = {"model": cfg["model"], "harness": harness, "run_name": cfg["run"]["name"], "run_id": cfg["run"].get("id"),
             "runtime": (agent_cfg.get("runtime") or {}).get("type"), "client_base_url": (cfg.get("client") or {}).get("base_url"),
             "num_rollouts": cfg.get("num_rollouts"), "ignore_timeouts": (cfg["env"].get("taskset") or {}).get("ignore_timeouts")}
    return rows, facts


def agent_and_model(trial: Path) -> tuple[str, str]:
    result = json.loads((trial / "result.json").read_text())
    agent = (result.get("agent_info") or {}).get("name") or (result.get("config") or {}).get("agent", {}).get("name")
    model = ((result.get("config") or {}).get("agent") or {}).get("model_name") or (
        (result.get("agent_info") or {}).get("model_info") or {}).get("name")
    return str(agent), str(model)


def convert(jobs: list[Path], out: Path, transcripts: bool, env_id: str, task_dir_root: Path | None,
            from_traces: Path | None = None) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    if from_traces is not None:
        rows, facts = traces_rows(from_traces)
        agent, model = facts["harness"], facts["model"]
        note = (f"verifiers 0.3.1 v1 run {facts['run_name']} ({agent} harness, {facts['runtime']} runtime), converted from "
                "traces.jsonl by scripts/harbor_to_prime_eval.py --from-traces; transcripts not included")
        jobs = [from_traces]
    else:
        trials = [t for job in jobs for t in trial_dirs(job)]
        if not trials:
            sys.exit(f"no trials (dirs with result.json) under {[str(j) for j in jobs]}")
        pairs = {agent_and_model(t) for t in trials}
        if len(pairs) != 1:
            sys.exit(f"one eval = one harness and one model; these jobs mix {sorted(pairs)}. Split them.")
        (agent, model), = pairs
        rows = [trial_row(t, transcripts, task_dir_root) for t in trials]
        note = (f"run through Harbor {HARBOR_VERSION} with the {agent} harness, converted by "
                "scripts/harbor_to_prime_eval.py; not a vf-eval run")
    if not rows:
        sys.exit("no rows")
    names = sorted({r["task"] for r in rows})
    index = {n: i for i, n in enumerate(names)}
    for r in rows:
        r["example_id"] = index[r["task"]]
    per_task = {n: [r["reward"] for r in rows if r["task"] == n] for n in names}
    metric_keys = sorted({k for r in rows for k in r["metrics"]})
    avg_metrics = {k: sum(r["metrics"][k] for r in rows if k in r["metrics"]) / sum(1 for r in rows if k in r["metrics"])
                   for k in metric_keys}
    seconds = [r["timing"]["total"]["seconds"] for r in rows if r["timing"]["total"] and r["timing"]["total"]["seconds"]]
    metadata = {
        "env_id": env_id,
        "env": env_id,
        "model": model,
        "harness": agent,
        "framework": "verifiers",  # the FILE format; the rollouts themselves came from Harbor, see `note`
        "note": note,
        **({"verifiers_run": facts} if facts else {}),
        "source_jobs": [j.name for j in jobs],
        "num_examples": len(names),
        "rollouts_per_example": max(len(v) for v in per_task.values()),
        "rollouts_per_example_by_task": {n: len(v) for n, v in per_task.items()},
        "tasks": names,
        "sampling_args": {},
        "env_args": {},
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "time": sum(seconds) if seconds else None,
        "avg_reward": sum(r["reward"] for r in rows) / len(rows),
        "avg_metrics": avg_metrics,
        "avg_error": sum(1 for r in rows if r["error"]) / len(rows),
        "pass_at_k": {n: float(any(v)) for n, v in per_task.items()},
        "transcripts_included": transcripts,
        "total_cost_usd": sum(r["cost_usd"] or 0 for r in rows),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    with (out / "results.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return metadata


def validate(out: Path) -> None:
    """The checks `prime eval push` runs before uploading (prime_cli/commands/evals.py), plus the size ceiling."""
    meta = json.loads((out / "metadata.json").read_text())
    assert (meta.get("env_id") or meta.get("env")) and "model" in meta, "metadata needs env_id and model"
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines() if l.strip()]
    assert rows and all(isinstance(r, dict) for r in rows), "results.jsonl must hold dict rows"
    assert all("example_id" in r or "id" in r for r in rows), "every row needs example_id"
    assert all("reward" in r for r in rows), "every row needs reward"
    biggest = max(len(json.dumps(r).encode()) for r in rows)
    assert biggest < 25 * 1024 * 1024, f"a row is {biggest} bytes; the samples endpoint caps a request at 25 MiB"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("jobs", nargs="*", type=Path, help="Harbor job dirs (each holds <trial>/result.json)")
    p.add_argument("--from-traces", type=Path, help="a verifiers v1 run dir (traces.jsonl + configs/resolved/eval.json) instead of jobs")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--env", default=ENV_ID, help="Prime Environments Hub slug the eval is filed under")
    p.add_argument("--transcripts", action="store_true", help="include agent transcripts (ATIF -> chat messages)")
    p.add_argument("--tasks-dir", type=Path, default=Path("tasks"), help="where <task>/instruction.md lives (prompt column)")
    a = p.parse_args()
    if bool(a.jobs) == (a.from_traces is not None):
        sys.exit("give Harbor job dirs, or --from-traces <run dir>, not both")
    meta = convert(a.jobs, a.out, a.transcripts, a.env, a.tasks_dir if a.tasks_dir.is_dir() else None, a.from_traces)
    validate(a.out)
    print(f"{a.out}: {meta['num_examples']} tasks, avg_reward={meta['avg_reward']:.3f}, model={meta['model']}, "
          f"harness={meta['harness']}, transcripts={meta['transcripts_included']}")
    print(f"push (Alex runs this):  prime eval push {a.out} --env {a.env} --name \"{a.out.name}\"")


if __name__ == "__main__":
    main()
