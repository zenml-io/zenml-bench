# /// script
# requires-python = ">=3.14"
# ///
"""Roll results/*.jsonl up into the per-task results table in README.md.

    uv run scripts/results_table.py            # rewrite the block between the results markers in README.md
    uv run scripts/results_table.py --print    # print the markdown only

One row per task; one column per model (bare condition only, so cells are comparable; skill/mcp rows live in the
results/*.md pages); median cost per trial across those bare trials; and a difficulty band computed from the numbers:
  saturated  every model passes >= 80 %
  headroom   some model passes between 20 % and 80 % (named)
  floor      every model passes < 20 %
Rows with reward null (trial crashed) are excluded from the pass rate but counted in the "crashed" note.
"""
import argparse
import json
import re
import statistics
import tomllib
from collections import defaultdict
from pathlib import Path

START, END = "<!-- results:start -->", "<!-- results:end -->"
SHORT = {"claude-opus-5": "opus-5", "gpt-5.6-terra": "gpt-5.6-terra", "claude-haiku-4-5-20251001": "haiku-4.5", "gpt-5.4-mini": "gpt-5.4-mini"}
ORDER = list(SHORT)


def short(model: str) -> str:
    return SHORT.get(model) or model.removeprefix("openrouter/")


def condition(row: dict) -> str:
    job = re.sub(r"-(cheap|l2|rerun)$", "", row["job"])
    return job.rsplit("-", 1)[1]


def load_rows() -> list[dict]:
    rows = [json.loads(l) for f in Path("results").glob("*.jsonl") for l in f.read_text().splitlines() if l.strip()]
    return [r for r in rows if r.get("model") and condition(r) == "bare"]


def band(rates: dict[str, tuple[int, int]]) -> str:
    ratios = {m: k / n for m, (k, n) in rates.items() if n}
    if not ratios:
        return "unmeasured"
    mid = [m for m, r in ratios.items() if 0.2 <= r <= 0.8]
    if mid:
        return "headroom (" + ", ".join(short(m) for m in mid) + ")"
    return "saturated" if all(r > 0.8 for r in ratios.values()) else "floor" if all(r < 0.2 for r in ratios.values()) else "mixed"


def table() -> str:
    rows = load_rows()
    tasks = sorted(p.parent.name for p in Path("tasks").glob("*/task.toml"))
    by_task: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        # Harbor truncates long task names in trial ids (r1-bare-clock-improve-within-bud__xxx), so match by prefix.
        prefix = r["trial"].split("__")[0]
        matches = [t for t in tasks if t.startswith(prefix)]
        by_task[min(matches, key=len) if matches else prefix].append(r)
    models = sorted({r["model"] for r in rows}, key=lambda m: (ORDER.index(m) if m in ORDER else 99, m))
    head = "| task | tier | " + " | ".join(short(m) for m in models) + " | median cost | band |"
    out = [head, "|" + "---|" * (len(models) + 4)]
    for t in tasks:
        meta = tomllib.loads((Path("tasks") / t / "task.toml").read_text()).get("metadata", {})
        rates: dict[str, tuple[int, int]] = {}
        for m in models:
            scored = [r for r in by_task[t] if r["model"] == m and r["reward"] is not None]
            if scored:
                rates[m] = (sum(int(float(r["reward"]) >= 1) for r in scored), len(scored))
        cells = [f"{k}/{n}" if (k := rates.get(m, (0, 0))[0]) is not None and m in rates and (n := rates[m][1]) else "–" for m in models]
        costs = [r["cost_usd"] for r in by_task[t] if r.get("cost_usd") is not None]
        cost = f"${statistics.median(costs):.2f}" if costs else "–"
        out.append(f"| `{t}` | {meta.get('tier', '?')} | " + " | ".join(cells) + f" | {cost} | {band(rates)} |")
    n_trials = len(rows)
    note = (
        f"Bare condition only (no skill, no MCP), {n_trials} trials, pass counts as passed/attempted per model. "
        "Three attempts per cell is a small sample: 3/3 against 2/3 is not a meaningful gap. Cost is the harness's own figure per trial "
        "at the prices of the run date, median over all bare trials of the task. Band: *saturated* = every model ≥ 80 %, *headroom* = a model "
        "sits in the 20–80 % band where a benchmark ranks agents and a trainer gets signal, *floor* = every model < 20 %. "
        "Per-condition tables, trajectories read by hand and what tripped each agent are in the `results/*.md` pages. Regenerate with `uv run scripts/results_table.py`."
    )
    return "\n".join(out) + "\n\n" + note + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()
    md = table()
    if a.print:
        print(md)
        return
    readme = Path("README.md")
    text = readme.read_text()
    block = f"{START}\n{md}{END}"
    if START in text and END in text:
        text = text[: text.index(START)] + block + text[text.index(END) + len(END):]
    else:
        text = text.replace("## License", f"## Results\n\n{block}\n\n## License", 1)
    readme.write_text(text)
    print(f"README.md results block updated ({md.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
