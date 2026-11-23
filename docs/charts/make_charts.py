# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Draw the charts in docs/zenml-bench.md and docs/kitaru-bench.md as standalone SVG files.

Run `uv run docs/charts/make_charts.py` after changing any chart's data below; it rewrites every
`docs/charts/*.svg`. The charts copy the look of the "Kaizen Benchmarks Today" page: story timelines
(labelled bars over days), run grids (one coloured cell per run) and flows (boxes with arrows).

GitHub strips inline <svg> from markdown, so the pages embed these files as images. Each file carries
its own light and dark palette and paints its own background, so it reads well in either theme.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent

STYLE = """
svg { --paper:#f3f5f2; --surface:#fbfcfa; --ink:#1b2422; --muted:#56635e; --rule:#d5ddd8; --accent:#17667a;
  --accent-soft:#dcebee; --ok:#a9cdb3; --fail:#c2412d; --warn:#d9a13a; --stale:#b7c0bc; --partial:#e08a6a;
  --commit:#2c4a52; --commit-ink:#f3f5f2; --fail-ink:#ffffff; }
@media (prefers-color-scheme: dark) {
  svg { --paper:#111816; --surface:#18201e; --ink:#e3ebe7; --muted:#9aaaa4; --rule:#2c3835; --accent:#6cc0d4;
    --accent-soft:#1c3339; --ok:#3f7a55; --fail:#e0634e; --warn:#d9a54a; --stale:#56625e; --partial:#e59a7c;
    --commit:#a9ccd4; --commit-ink:#111816; --fail-ink:#111816; }
}
text { font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: var(--ink); }
.mono { font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace; }
.bg { fill: var(--surface); stroke: var(--rule); }
.title { font-size: 15px; font-weight: 600; }
.axis { font-size: 11px; fill: var(--muted); }
.row-label { font-size: 12px; }
.bar-label { font-size: 11.5px; }
.note { font-size: 11px; fill: var(--muted); }
.legend { font-size: 12px; fill: var(--muted); }
.gridline { stroke: var(--rule); stroke-width: 1; }
.k-problem { fill: var(--fail); } .k-decoy { fill: var(--warn); } .k-partial { fill: var(--partial); }
.k-neutral { fill: var(--stale); } .k-ok { fill: var(--ok); } .k-fail { fill: var(--fail); }
.k-cached { fill: var(--stale); } .k-plain { fill: var(--paper); stroke: var(--rule); } .k-commit { fill: var(--commit); } .k-accent { fill: var(--accent); }
.ring { fill: none; stroke: var(--accent); stroke-width: 3; }
.box { fill: var(--paper); stroke: var(--rule); }
.box-hot { fill: var(--paper); stroke: var(--fail); stroke-width: 2; }
.box-good { fill: var(--paper); stroke: var(--accent); stroke-width: 2; }
.box-name { font-size: 12.5px; font-weight: 600; fill: var(--accent); }
.box-text { font-size: 11.5px; fill: var(--muted); }
.arrow { stroke: var(--muted); stroke-width: 1.5; fill: none; marker-end: url(#arrowhead); }
.commit-label { font-size: 10px; font-weight: 600; fill: var(--commit-ink); }
.cell-text { font-size: 11px; font-weight: 600; fill: var(--ink); }
.cell-text-inv { font-size: 11px; font-weight: 600; fill: var(--fail-ink); }
"""

LEGEND_TEXT = {
    "problem": "the cause a task is after", "decoy": "a decoy: looks guilty, isn't", "partial": "a partial fix",
    "neutral": "background or symptom", "ok": "completed", "fail": "failed", "cached": "served from the cache",
    "commit": "git commit", "ring": "what the grader checks",
}

W = 920  # every chart is this wide


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def text_w(s: str, size: float = 11.5) -> float:
    """Rough rendered width of sans-serif text; good enough to keep labels inside the chart."""
    return sum(0.33 if c in " .,:;'|!il()" else 0.62 if c.isupper() else 0.54 for c in s) * size


def wrap(s: str, width: float, size: float = 11.5) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and text_w(trial, size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def doc(height: float, title: str, body: list[str]) -> str:
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height:.0f}" width="{W}" height="{height:.0f}" role="img" aria-label="{esc(title)}">',
        f"<title>{esc(title)}</title>", f"<style>{STYLE}</style>",
        '<defs><marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#8a9893"/></marker></defs>',
        f'<rect class="bg" x="0.5" y="0.5" width="{W - 1}" height="{height - 1:.0f}" rx="10"/>',
        f'<text class="title" x="20" y="28">{esc(title)}</text>', *body, "</svg>", ""])


def legend(kinds: list[str], y: float) -> list[str]:
    out, x = [], 20.0
    for k in kinds:
        label = LEGEND_TEXT[k]
        if k == "ring":
            out.append(f'<rect class="ring" x="{x + 1.5}" y="{y - 10.5}" width="11" height="11" rx="2"/>')
        else:
            out.append(f'<rect class="k-{k}" x="{x}" y="{y - 12}" width="14" height="14" rx="3"/>')
        out.append(f'<text class="legend" x="{x + 20}" y="{y}">{esc(label)}</text>')
        x += 20 + text_w(label, 12) + 22
    return out


# ---------------------------------------------------------------- story timelines (bars over days)

@dataclass(frozen=True)
class Bar:
    start: date
    end: date  # inclusive; start == end draws one day
    kind: str  # problem | decoy | partial | neutral | commit
    label: str = ""


@dataclass(frozen=True)
class Row:
    label: str
    bars: list[Bar]


def story_chart(name: str, title: str, start: date, end: date, rows: list[Row], ticks: list[date],
                note: str = "") -> None:
    left, right, top, row_h = 190.0, W - 24.0, 64.0, 46.0
    days = (end - start).days + 1
    dx = (right - left) / days
    x_of = lambda d: left + (d - start).days * dx  # noqa: E731
    height = top + len(rows) * row_h + 58 + (18 if note else 0)
    body = []
    for t in ticks:
        x = x_of(t) + dx / 2
        body += [f'<text class="axis" x="{x:.1f}" y="{top - 12}" text-anchor="middle">{t.day} {t:%b}</text>',
                 f'<line class="gridline" x1="{x:.1f}" x2="{x:.1f}" y1="{top - 6}" y2="{top + len(rows) * row_h - 8}"/>']
    for i, row in enumerate(rows):
        y = top + i * row_h + 20
        body.append(f'<text class="row-label" x="{left - 12}" y="{y + 11}" text-anchor="end">{esc(row.label)}</text>')
        for b in row.bars:
            x0, x1 = x_of(b.start), x_of(b.end) + dx
            if b.kind == "commit":
                cx = (x0 + x1) / 2
                body.append(f'<rect class="k-commit" x="{cx - 8:.1f}" y="{y}" width="16" height="14" rx="3"/>')
                if len(b.label) <= 2:  # a short label is a number drawn inside the marker; explain it in the note
                    body.append(f'<text class="commit-label" x="{cx:.1f}" y="{y + 10.5}" text-anchor="middle">{esc(b.label)}</text>')
                    continue
                x0 = x1 = cx
            else:
                body.append(f'<rect class="k-{b.kind}" x="{x0 + 1:.1f}" y="{y}" width="{x1 - x0 - 2:.1f}" height="14" rx="3"/>')  # 2px gap between neighbours
            if b.label:
                tw = text_w(b.label)
                if x0 + 2 + tw <= right:
                    body.append(f'<text class="bar-label" x="{x0 + 2:.1f}" y="{y - 5}">{esc(b.label)}</text>')
                else:
                    body.append(f'<text class="bar-label" x="{min(x1, right):.1f}" y="{y - 5}" text-anchor="end">{esc(b.label)}</text>')
    if note:
        body.append(f'<text class="note" x="20" y="{height - 44}">{esc(note)}</text>')
    kinds = [k for k in ("problem", "decoy", "partial", "neutral", "commit") if any(b.kind == k for r in rows for b in r.bars)]
    body += legend(kinds, height - 18)
    (OUT / f"{name}.svg").write_text(doc(height, title, body))


# ---------------------------------------------------------------- run grids (one cell per run)

@dataclass(frozen=True)
class Cell:
    status: str  # ok | fail | cached | plain
    inside: str = ""  # short text drawn inside the cell
    below: str = ""  # explanation under the cell
    ring: bool = False  # the run the grader wants


@dataclass(frozen=True)
class GridRow:
    label: str
    cells: list[Cell | None]


@dataclass(frozen=True)
class Panel:
    heading: str
    rows: list[GridRow]
    verdict: str = ""


def grid_chart(name: str, title: str, columns: list[str], panels: list[Panel], note: str = "",
               legend_kinds: tuple[str, ...] = ("ok", "fail", "ring")) -> None:
    left, right = 170.0, W - 20.0
    col_w = (right - left) / len(columns)
    cell_w, cell_h = min(col_w - 10, 140), 28
    body, y = [], 52.0
    for j, c in enumerate(columns):
        body.append(f'<text class="axis mono" x="{left + j * col_w + col_w / 2:.1f}" y="{y + 6}" text-anchor="middle">{esc(c)}</text>')
    y += 22
    for p in panels:
        if p.heading:
            body.append(f'<text class="row-label" x="20" y="{y + 12}" font-weight="600">{esc(p.heading)}</text>')
            y += 24
        for r in p.rows:
            lines = max([len(wrap(c.below, col_w - 6, 11)) for c in r.cells if c] + [0])
            body.append(f'<text class="row-label" x="{left - 12}" y="{y + cell_h / 2 + 4}" text-anchor="end">{esc(r.label)}</text>')
            for j, c in enumerate(r.cells):
                if c is None:
                    continue
                cx = left + j * col_w + (col_w - cell_w) / 2
                body.append(f'<rect class="k-{c.status}" x="{cx:.1f}" y="{y}" width="{cell_w:.1f}" height="{cell_h}" rx="5"/>')
                if c.ring:
                    body.append(f'<rect class="ring" x="{cx - 3:.1f}" y="{y - 3}" width="{cell_w + 6:.1f}" height="{cell_h + 6}" rx="7"/>')
                if c.inside:
                    cls = "cell-text-inv" if c.status == "fail" else "cell-text"
                    body.append(f'<text class="{cls}" x="{cx + cell_w / 2:.1f}" y="{y + cell_h / 2 + 4}" text-anchor="middle">{esc(c.inside)}</text>')
                for k, line in enumerate(wrap(c.below, col_w - 6, 11)):
                    body.append(f'<text class="note" x="{cx + cell_w / 2:.1f}" y="{y + cell_h + 15 + k * 13}" text-anchor="middle">{esc(line)}</text>')
            y += cell_h + 16 + lines * 13
        if p.verdict:
            body.append(f'<text class="row-label" x="{left}" y="{y + 4}" font-weight="600">{esc(p.verdict)}</text>')
            y += 24
        y += 6
    if note:
        for k, line in enumerate(wrap(note, W - 40, 11)):
            body.append(f'<text class="note" x="20" y="{y + 8 + k * 14}">{esc(line)}</text>')
        y += 14 * len(wrap(note, W - 40, 11)) + 6
    height = y + 40
    body += legend(list(legend_kinds), height - 16)
    (OUT / f"{name}.svg").write_text(doc(height, title, body))


# ---------------------------------------------------------------- flows (boxes with arrows)

@dataclass(frozen=True)
class Box:
    name: str
    text: str = ""
    kind: str = ""  # "" | hot (the fault, or where things go wrong) | good (what the grader trusts)


@dataclass(frozen=True)
class Lane:
    heading: str
    stages: list[Box | list[Box]]  # a list = boxes stacked in one column (a branch)


def flow_chart(name: str, title: str, lanes: list[Lane], note: str = "") -> None:
    body, y = [], 50.0
    for lane in lanes:
        if lane.heading:
            body.append(f'<text class="row-label" x="20" y="{y + 12}" font-weight="600">{esc(lane.heading)}</text>')
            y += 22
        n, gap = len(lane.stages), 30.0
        bw = (W - 40 - gap * (n - 1)) / n
        cols = [s if isinstance(s, list) else [s] for s in lane.stages]
        heights = [[46 + 14 * len(wrap(b.text, bw - 20)) for b in col] for col in cols]
        tallest = max(h[0] for h in heights if len(h) == 1) if any(len(h) == 1 for h in heights) else 0
        heights = [[tallest] if len(h) == 1 else h for h in heights]  # single boxes in a lane share one height
        lane_h = max(sum(h) + 10 * (len(h) - 1) for h in heights)
        for j, col in enumerate(cols):
            x = 20 + j * (bw + gap)
            stack_h = sum(heights[j]) + 10 * (len(col) - 1)
            by = y + (lane_h - stack_h) / 2
            for b, bh in zip(col, heights[j]):
                cls = {"hot": "box-hot", "good": "box-good"}.get(b.kind, "box")
                body.append(f'<rect class="{cls}" x="{x:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh}" rx="8"/>')
                body.append(f'<text class="box-name mono" x="{x + 10:.1f}" y="{by + 20:.1f}">{esc(b.name)}</text>')
                for k, line in enumerate(wrap(b.text, bw - 20)):
                    body.append(f'<text class="box-text" x="{x + 10:.1f}" y="{by + 38 + k * 14:.1f}">{esc(line)}</text>')
                if j + 1 < n:  # arrow from the middle of each box to the next column's middle
                    nxt = y + lane_h / 2
                    body.append(f'<path class="arrow" d="M{x + bw + 2:.1f} {by + bh / 2:.1f} C{x + bw + gap / 2:.1f} {by + bh / 2:.1f} {x + bw + gap / 2:.1f} {nxt:.1f} {x + bw + gap - 3:.1f} {nxt:.1f}"/>')
                by += bh + 10
        y += lane_h + 22
    if note:
        for k, line in enumerate(wrap(note, W - 40, 11)):
            body.append(f'<text class="note" x="20" y="{y + 4 + k * 14}">{esc(line)}</text>')
        y += 14 * len(wrap(note, W - 40, 11))
    (OUT / f"{name}.svg").write_text(doc(y + 16, title, body))


def d(s: str) -> date:
    return date.fromisoformat(s)


# ================================================================ ZenML Bench charts

def zenml_charts() -> None:
    flow_chart("zb-how-a-run-works", "How one ZenML Bench attempt runs", [
        Lane("Image build, once per task", [
            Box("base image", "Python 3.14, ZenML 0.96.4, agent CLIs, offline docs, the ZenML MCP server"),
            Box("task image", "copies the project to /app and runs zenml init"),
            Box("setup_store.sh", "optional: registers stacks, or runs the real pipeline to make history"),
        ]),
        Lane("One attempt", [
            Box("agent", "reads instruction.md, edits and runs the project; 30 minutes; network: model API only"),
            Box("grader", "runs the agent's entrypoint on data the agent never saw", "good"),
            Box("ZenML store", "runs, step statuses, artifacts, model versions, compiled settings", "good"),
            Box("reward", "1 or 0"),
        ]),
    ])

    flow_chart("zb-nightly", "nightly: pipeline nightly_training(path)", [Lane("", [
        Box("load_data(path)", "cache key = code + the path string, not the file's contents", "hot"),
        Box("train(df)", "expensive (sleeps 3 s); output: model"),
        Box("evaluate(model, df)", "output: score; also reads df directly"),
    ])], note="Replace the file at data/train.csv and the key does not change, so load_data and everything after it come from the cache.")

    grid_chart("zb-b3-grading", "B3: how the grader checks the cache (five runs, fixtures a a b b c)",
               ["run 1", "run 2", "run 3", "run 4", "run 5"], [
        Panel("A correct fix: the cache follows the file's contents", [
            GridRow("data file", [Cell("plain", "a"), Cell("plain", "a"), Cell("plain", "b"), Cell("plain", "b"), Cell("plain", "c")]),
            GridRow("load_data", [Cell("ok", "ran"), Cell("cached", "cached"), Cell("ok", "ran"), Cell("cached", "cached"), Cell("ok", "ran")]),
            GridRow("train", [Cell("ok", "ran"), Cell("cached", "cached", ring=True), Cell("ok", "ran", ring=True), Cell("cached", "cached", ring=True), Cell("ok", "ran", ring=True)]),
        ], "Scores right on every run, train cached exactly when the data did not change: reward 1"),
        Panel("The obvious fix: enable_cache=False on load_data", [
            GridRow("load_data", [Cell("ok", "ran"), Cell("ok", "ran"), Cell("ok", "ran"), Cell("ok", "ran"), Cell("ok", "ran")]),
            GridRow("train", [Cell("ok", "ran"), Cell("fail", "ran", "new artifact id, so a cache miss"), Cell("ok", "ran"), Cell("fail", "ran", "same again"), Cell("ok", "ran")]),
        ], "Scores are right, but train reruns every time: reward 0"),
    ], note="A freshly loaded DataFrame is a new artifact with a new id, and the pandas materializer has no content hash, so train's cache key changes even when the data is identical.",
       legend_kinds=("ok", "cached", "fail", "ring"))

    flow_chart("zb-sampling", "sampling: pipeline qa_sampling(n)", [Lane("", [
        Box("load_events()", "expensive (sleeps 3 s); should stay cached"),
        Box("sample_events(events, n)", "df.sample(n) with no seed; cached, so every QA review gets the same events", "hot"),
        Box("review_report(sample)", "must describe the sample from the same run"),
    ])])

    flow_chart("zb-training", "legacy_training (B9) and k8s_training (B7): the same four steps", [Lane("", [
        Box("load_data", "outputs: features, labels"),
        Box("split(test_size, seed)", "outputs: x_train, x_test, y_train, y_test"),
        Box("train(C)", "output: model; B7 puts this step's pod on a GPU node"),
        Box("evaluate", "output: score"),
    ])], note="legacy_training is written in the ZenML 0.4x API: BaseParameters, Output(...) annotations, post_execution.")

    flow_chart("zb-daily-report", "daily_report: pipeline daily_report(date)", [Lane("", [
        Box("load(date)", "reads data/<date>.csv; never cached in daily_report_hard"),
        Box("parse", "strict timestamps; amount as float, so \"1,234.50\" raises"),
        Box("summarise", "rows, total, per-region totals; daily_report_hard rejects unknown regions"),
        Box("write_report", "writes reports/<date>.json"),
    ])], note="run.py --trigger scheduled names the run scheduled-<date> and tags it scheduled; a run started by hand is manual-<date>-<time>, tagged manual.")

    days10 = ["09-05", "09-06", "09-07", "09-08", "09-09", "typo"]
    grid_chart("zb-b10-history", "B10: the six runs in the store when the agent starts", days10, [Panel("", [
        GridRow("scheduled", [Cell("fail", "failed", "load: no export delivered"), Cell("fail", "failed", "write_report: no reports/ folder"),
                              Cell("ok", "completed"), Cell("ok", "completed"),
                              Cell("fail", "failed", "parse: thousands separators in amounts", ring=True), None]),
        GridRow("manual", [None, None, None, None, None, Cell("fail", "failed", "started by hand for 2026-09-31; load fails")]),
    ])], note="The most recent failed run is the hand-started typo, not the scheduled run the instruction means. Only the 09-09 failure is a code fault.")

    cols10h = ["08-30", "09-02", "09-03", "09-04", "09-05", "09-06", "09-07", "09-08", "09-09", "typo"]
    grid_chart("zb-b10h-history", "B10H: ten runs; two of the failures are code faults", cols10h, [Panel("", [
        GridRow("scheduled", [None, Cell("ok", "ok"), Cell("fail", "failed", "summarise: regions \"North\", \"west \"", ring=True), Cell("ok", "ok"),
                              Cell("fail", "failed", "load: no export"), Cell("fail", "failed", "write_report: folder gone"),
                              Cell("ok", "ok"), Cell("ok", "ok"), Cell("fail", "failed", "parse: separators; \"this morning\"", ring=True), None]),
        GridRow("manual", [Cell("fail", "failed", "parse: old ISO timestamps"), None, None, None, None, None, None, None, None,
                           Cell("fail", "failed", "load: typo date")]),
    ])], note="The 09-03 and 09-09 exports are moved off the box after they fail, so the cause can only be read from the recorded traceback or from the load step's output artifact.")

    cols14 = ["08-24", "08-25", "08-26", "08-27", "08-28", "09-05", "09-06", "09-07", "09-08", "09-09"]
    grid_chart("zb-b14-history", "B14: which completed backfill run had the largest total?", cols14, [Panel("", [
        GridRow("backfill", [Cell("ok", "ok"), Cell("ok", "ok"), Cell("fail", "failed", "largest total of all, but write_report failed"),
                             Cell("ok", "ok", "the answer", ring=True), Cell("fail", "failed", "load: no export")] + [None] * 5),
        GridRow("scheduled", [None] * 5 + [Cell("fail", "failed"), Cell("ok", "ok"), Cell("ok", "ok"),
                                          Cell("ok", "ok", "beats every backfill day, but not a backfill"), Cell("fail", "failed")]),
    ])], note="The backfill runs were started by hand and tagged backfill afterwards. A typo run for 2026-09-31 (failed, tagged manual) is also in the store.")

    grid_chart("zb-b14h-history", "B14H: re-processed days, and the rule \"the latest completed processing counts\"",
               ["08-24", "08-25", "08-26", "08-27", "08-28", "09-08"], [Panel("", [
        GridRow("first processing", [Cell("ok", "ok"), Cell("ok", "ok", "still counts: its v2 failed"),
                                     Cell("fail", "failed", "largest summary of all"), Cell("ok", "ok", "superseded by its v2"),
                                     Cell("fail", "failed", "no export"), None]),
        GridRow("re-processed (v2)", [None, Cell("fail", "failed", "latest, but failed"), Cell("ok", "ok", "the answer: summarise output version 5", ring=True),
                                      Cell("ok", "ok", "counts for 08-27"), None, None]),
        GridRow("scheduled", [None] * 5 + [Cell("ok", "ok", "largest completed run, but not a backfill")]),
    ])], note="Each simpler rule lands on a different run: largest summary (08-26 first), largest completed (08-27 first), latest processing (08-25 v2), any run (09-08).")

    flow_chart("zb-model-promotion", "model_promotion: two pipelines share the model demand_forecaster", [
        Lane("train_forecaster(algorithm)", [
            Box("load_train", "train and validation split"),
            Box("train", "linear (version 1, better) or random forest (version 2, worse)"),
            Box("evaluate", "val_mae, logged on the model version"),
        ]),
        Lane("batch_forecast(input_path)", [
            Box("load_batch", "reads the batch CSV"),
            Box("predict", "loads the model version inside the step; the version is not in the cache key", "hot"),
            Box("predictions", "must come from whichever version holds production when the run starts", "good"),
        ]),
    ], note="At build: train version 1, train version 2, run inference once (it reads \"latest\", version 2).")

    flow_chart("zb-research-chain", "R1 and R2: the chain the grader walks before it trusts a model", [Lane("", [
        Box("production version", "of research_model"),
        Box("linked run", "of the research pipeline, status completed"),
        Box("train step", "of that run; also recorded n_train_rows and a digest of the rows"),
        Box("model output", "produced by that same step, not attached later"),
        Box("hidden data", "the grader's own evaluator scores it: gap_closed", "good"),
    ])], note="ZenML lets you attach any artifact to any model version, so a link alone proves nothing. A model that breaks the chain is not scored.")


# ================================================================ Kitaru Bench charts

def kitaru_charts() -> None:
    flow_chart("kb-how-a-run-works", "How one Kitaru Bench attempt runs", [
        Lane("Image build, once per task", [
            Box("base image", "Kitaru 0.27.7, PostgreSQL, agent CLIs, plugin wheels, offline docs"),
            Box("world section", "load.py imports or records the history story.py planned"),
            Box("task section", "optional setup/: an agent version, a cohort, earlier imports"),
        ]),
        Lane("One attempt", [
            Box("start.sh", "healthcheck starts Postgres, the Kitaru server and a worker"),
            Box("agent", "user 'agent', over HTTP only; 30 minutes, 2 CPUs"),
            Box("grader", "root; stops the agent's processes, starts its own worker as 'grader'", "good"),
            Box("checks", "Kitaru's records, finance rows, the agent's code on hidden inputs", "good"),
            Box("reward", "1 or 0"),
        ]),
    ])

    story_chart("kb-storefront", "storefront: Larkspur Goods returns assistant, 1 June to 30 July 2026",
                d("2026-06-01"), d("2026-07-30"), [
        Row("agent release", [Bar(d("2026-06-01"), d("2026-06-30"), "neutral", "1.3.0"),
                              Bar(d("2026-07-01"), d("2026-07-21"), "neutral", "1.4.0"),
                              Bar(d("2026-07-22"), d("2026-07-30"), "neutral", "1.4.1")]),
        Row("reply text", [Bar(d("2026-07-01"), d("2026-07-30"), "problem", "euro card refunds quoted 100x (the money is right)")]),
        Row("standing faults", [Bar(d("2026-06-01"), d("2026-07-30"), "neutral", "too many lookups, late and double refunds, curt replies, idle timeouts")]),
        Row("refunds (diag.)", [Bar(d("2026-06-15"), d("2026-06-28"), "problem", "full refunds also pay a shipping fee")]),
        Row("order service (diag.)", [Bar(d("2026-06-21"), d("2026-06-21"), "problem", "21 Jun: down 10:00-20:00, retries")]),
        Row("traffic (diag.)", [Bar(d("2026-07-04"), d("2026-07-04"), "problem", "4 Jul: summer-sale, +120 ordinary conversations")]),
        Row("served model (diag.)", [Bar(d("2026-07-09"), d("2026-07-12"), "partial", "9 Jul: dated snapshot served to ~35%, from 13 Jul to all"),
                                     Bar(d("2026-07-13"), d("2026-07-18"), "problem")]),
        Row("polite-closing check", [Bar(d("2026-06-01"), d("2026-07-30"), "decoy", "fails idle timeouts, where nothing went wrong")]),
    ], [d("2026-06-01"), d("2026-06-15"), d("2026-07-01"), d("2026-07-15"), d("2026-07-30")],
       note="Rows marked (diag.) exist only in the diagnosis history used by C1h and the D tasks. Amber = a decoy for the diagnosis and checks tasks.")

    story_chart("kb-clinic", "clinic: Fernhill Vets appointment assistant, 1 June to 20 July 2026",
                d("2026-06-01"), d("2026-07-20"), [
        Row("agent release", [Bar(d("2026-06-01"), d("2026-06-20"), "neutral", "1.1.0"),
                              Bar(d("2026-06-21"), d("2026-06-24"), "decoy", "1.2.0 rolls out"),
                              Bar(d("2026-06-25"), d("2026-07-08"), "neutral", ""),
                              Bar(d("2026-07-09"), d("2026-07-20"), "partial", "1.3.0: half a fix")]),
        Row("git commits", [Bar(d("2026-06-20"), d("2026-06-20"), "commit", "1"), Bar(d("2026-06-26"), d("2026-06-26"), "commit", "2"),
                            Bar(d("2026-07-01"), d("2026-07-01"), "commit", "3"), Bar(d("2026-07-08"), d("2026-07-08"), "commit", "4")]),
        Row("scheduling service", [Bar(d("2026-06-15"), d("2026-07-20"), "problem", "15 Jun: books the neighbouring clinic, about 7 in 10")]),
        Row("search", [Bar(d("2026-06-15"), d("2026-07-08"), "neutral", "searches twice (symptom)")]),
        Row("complaints", [Bar(d("2026-06-17"), d("2026-07-20"), "decoy", "13 customers complain (not the bad bookings)")]),
        Row("traffic mix", [Bar(d("2026-06-22"), d("2026-07-20"), "problem", "22 Jun: partner portal sends new patients, 3x the calls")]),
        Row("group bookings", [Bar(d("2026-06-27"), d("2026-07-20"), "problem", "27 Jun: 4-7 animals, correctly refused (422)")]),
        Row("reply length", [Bar(d("2026-07-01"), d("2026-07-20"), "problem", "1 Jul: long replies cut off")]),
    ], [d("2026-06-01"), d("2026-06-15"), d("2026-07-01"), d("2026-07-15")],
       note="Commits: 1 release 1.2.0 (shorter greeting); 2 prompt wording for the litter offer; 3 config: max_tokens 400 -> 120, no release; 4 release 1.3.0.")

    story_chart("kb-exports-nightly", "exports: the nightly import before I4 starts, 1 to 8 August 2026",
                d("2026-08-01"), d("2026-08-08"), [
        Row("script v1", [Bar(d("2026-08-01"), d("2026-08-05"), "neutral", "nights 1-5: identity tidewater-support, correct")]),
        Row("cohort", [Bar(d("2026-08-05"), d("2026-08-05"), "neutral", "reviewed-week-31 created")]),
        Row("commit", [Bar(d("2026-08-05"), d("2026-08-05"), "commit", "5 Aug: identity taken from the file name")]),
        Row("script v2", [Bar(d("2026-08-06"), d("2026-08-07"), "problem", "nights 6-7: 96 stray sessions")]),
        Row("grader", [Bar(d("2026-08-08"), d("2026-08-08"), "neutral", "night 8, run twice")]),
    ], [d(f"2026-08-0{i}") for i in range(1, 9)],
       note="Each night's file holds the day before and the day itself. The 48 tickets of days 6 and 7 exist only as strays.")

    flow_chart("kb-replay", "helpdesk worlds: what a replay does with each tool call", [Lane("", [
        Box("recorded conversation", "every model and tool call, recorded by Kitaru's adapter"),
        Box("replay", "re-runs the agent (a newer release, a different setting)"),
        Box("tool policy", "decided per tool; the default is live"),
        [Box("recorded", "answer from the recording; nothing leaves the box", "good"),
         Box("live", "real call: issue_refund reaches the finance service, which appends a row; a customer is paid again", "hot")],
    ])], note="Every replay task counts the finance service's rows before and after. One new row scores 0.")


if __name__ == "__main__":
    zenml_charts()
    kitaru_charts()
    print("\n".join(sorted(p.name for p in OUT.glob("*.svg"))))
