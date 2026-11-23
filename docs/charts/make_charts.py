# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Draw the charts in docs/zenml-bench.md and docs/kitaru-bench.md as standalone SVG files.

Run `uv run docs/charts/make_charts.py` after changing any chart's data below; it rewrites every
`docs/charts/*.svg`. The charts follow the calm editorial palette of the "Kaizen Benchmarks Today"
page: overview matrices, story timelines, run grids, flows, and directory trees.

GitHub strips inline <svg> from markdown, so the pages embed these files as images. Each file carries
its own light and dark palette and paints its own background, so it reads well in either theme.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from pathlib import Path

OUT = Path(__file__).parent

STYLE = """
svg { --paper:#f3f5f2; --surface:#fbfcfa; --ink:#1b2422; --muted:#56635e; --rule:#d5ddd8; --accent:#17667a;
  --accent-soft:#dcebee; --ok:#a9cdb3; --fail:#c2412d; --warn:#d9a13a; --stale:#b7c0bc; --partial:#e08a6a;
  --commit:#2c4a52; --commit-ink:#f3f5f2; --fail-ink:#ffffff; --band:#e9efec; --warn-soft:#f6ebd4; --fail-soft:#f7e2de; }
@media (prefers-color-scheme: dark) {
  svg { --paper:#111816; --surface:#18201e; --ink:#e3ebe7; --muted:#9aaaa4; --rule:#2c3835; --accent:#6cc0d4;
    --accent-soft:#1c3339; --ok:#3f7a55; --fail:#e0634e; --warn:#d9a54a; --stale:#56625e; --partial:#e59a7c;
    --commit:#a9ccd4; --commit-ink:#111816; --fail-ink:#111816; --band:#1e2926; --warn-soft:#332b1c; --fail-soft:#351f1c; }
}
text { font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: var(--ink); }
.mono { font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace; }
.bg { fill: var(--surface); stroke: var(--rule); }
.title { font-size: 15px; font-weight: 600; }
.subtitle { font-size: 12px; fill: var(--muted); }
.axis { font-size: 11px; fill: var(--muted); }
.row-label { font-size: 12px; }
.bar-label { font-size: 11.5px; }
.note { font-size: 11px; fill: var(--muted); }
.legend { font-size: 11.5px; fill: var(--muted); }
.gridline { stroke: var(--rule); stroke-width: 1; }
.dashed { stroke: var(--rule); stroke-width: 1.25; stroke-dasharray: 4 3; fill: none; }
.band { fill: var(--band); stroke: none; }
.k-problem { fill: var(--fail); } .k-decoy { fill: var(--warn); } .k-partial { fill: var(--partial); }
.k-neutral { fill: var(--stale); } .k-ok { fill: var(--ok); } .k-fail { fill: var(--fail); }
.k-cached { fill: var(--stale); } .k-plain { fill: var(--paper); stroke: var(--rule); }
.k-commit { fill: var(--commit); } .k-accent { fill: var(--accent); } .k-accent-soft { fill: var(--accent-soft); stroke: var(--accent); }
.k-warn-soft { fill: var(--warn-soft); stroke: var(--warn); } .k-fail-soft { fill: var(--fail-soft); stroke: var(--fail); }
.ring { fill: none; stroke: var(--accent); stroke-width: 2.5; }
.box { fill: var(--paper); stroke: var(--rule); }
.box-hot { fill: var(--paper); stroke: var(--fail); stroke-width: 2; }
.box-good { fill: var(--paper); stroke: var(--accent); stroke-width: 2; }
.box-warn { fill: var(--paper); stroke: var(--warn); stroke-width: 2; }
.box-soft { fill: var(--accent-soft); stroke: var(--accent); stroke-width: 1.5; }
.box-name { font-size: 12.5px; font-weight: 600; fill: var(--accent); }
.box-name-hot { font-size: 12.5px; font-weight: 600; fill: var(--fail); }
.box-name-warn { font-size: 12.5px; font-weight: 600; fill: var(--warn); }
.box-text { font-size: 11.5px; fill: var(--muted); }
.arrow { stroke: var(--muted); stroke-width: 1.5; fill: none; marker-end: url(#arrowhead); }
.arrow-accent { stroke: var(--accent); stroke-width: 1.75; fill: none; marker-end: url(#arrowhead-accent); }
.arrow-hot { stroke: var(--fail); stroke-width: 1.75; fill: none; marker-end: url(#arrowhead-hot); }
.commit-label { font-size: 10px; font-weight: 600; fill: var(--commit-ink); }
.cell-text { font-size: 11px; font-weight: 600; fill: var(--ink); }
.cell-text-inv { font-size: 11px; font-weight: 600; fill: var(--fail-ink); }
.pill { fill: var(--accent-soft); stroke: none; }
.pill-text { font-size: 10.5px; font-weight: 600; fill: var(--accent); }
.pill-hot { fill: var(--fail-soft); stroke: var(--fail); stroke-width: 1; }
.pill-hot-text { font-size: 10.5px; font-weight: 600; fill: var(--fail); }
.section-head { font-size: 12px; font-weight: 600; fill: var(--ink); }
"""

DEFAULT_LEGEND = {
    "problem": "what a task must find",
    "decoy": "decoy (looks guilty, isn't)",
    "partial": "partial fix or partial rollout",
    "neutral": "background or symptom",
    "ok": "completed",
    "fail": "failed",
    "cached": "served from cache",
    "commit": "git commit",
    "ring": "what the grader checks",
    "box-good": "grader / verified boundary",
    "box-hot": "trap / failure point",
}

W = 940  # every chart uses this width


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def text_w(s: str, size: float = 11.5) -> float:
    """Rough rendered width of sans-serif text; conservative enough to avoid overflow."""
    return sum(0.35 if c in " .,:;'|!il()" else 0.65 if c.isupper() else 0.57 for c in s) * size


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


def doc(height: float, title: str, body: list[str], subtitle: str = "") -> str:
    head = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height:.0f}" width="{W}" height="{height:.0f}" role="img" aria-label="{esc(title)}">',
        f"<title>{esc(title)}</title>",
        f"<style>{STYLE}</style>",
        "<defs>"
        '<marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#8a9893"/></marker>'
        '<marker id="arrowhead-accent" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#17667a"/></marker>'
        '<marker id="arrowhead-hot" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#c2412d"/></marker>'
        "</defs>",
        f'<rect class="bg" x="0.5" y="0.5" width="{W - 1}" height="{height - 1:.0f}" rx="10"/>',
        f'<text class="title" x="20" y="28">{esc(title)}</text>',
    ]
    if subtitle:
        head.append(f'<text class="subtitle" x="20" y="46">{esc(subtitle)}</text>')
    return "\n".join([*head, *body, "</svg>", ""])


def legend(items: list[tuple[str, str]], y: float) -> list[str]:
    out, x = [], 20.0
    for k, label in items:
        if k == "ring":
            out.append(f'<rect class="ring" x="{x + 1.5}" y="{y - 10.5}" width="11" height="11" rx="2"/>')
        elif k in ("box-good", "box-hot", "box-warn"):
            out.append(f'<rect class="{k}" x="{x + 1}" y="{y - 11}" width="12" height="12" rx="3"/>')
        else:
            out.append(f'<rect class="k-{k}" x="{x}" y="{y - 11}" width="13" height="13" rx="3"/>')
        out.append(f'<text class="legend" x="{x + 19}" y="{y}">{esc(label)}</text>')
        x += 19 + text_w(label, 11.5) + 20
    return out


def d(s: str) -> date:
    return date.fromisoformat(s)


# ---------------------------------------------------------------- story timelines


@dataclass(frozen=True)
class Bar:
    start: date
    end: date
    kind: str  # problem | decoy | partial | neutral | commit
    label: str = ""
    highlight: bool = False  # accent outline on commits or bars


@dataclass(frozen=True)
class Row:
    label: str
    bars: list[Bar]
    tag: str = ""  # task tag pill on the left, e.g. "D2"


def story_chart(
    name: str,
    title: str,
    start: date,
    end: date,
    rows: list[Row],
    ticks: list[date],
    subtitle: str = "",
    note: str = "",
    legend_overrides: dict[str, str] | None = None,
) -> None:
    left, right = 216.0, W - 24.0
    top = 82.0 if subtitle else 64.0
    row_h = 46.0
    days = (end - start).days + 1
    dx = (right - left) / days
    x_of = lambda dt: left + (dt - start).days * dx  # noqa: E731
    note_lines = wrap(note, W - 40, 11) if note else []
    height = top + len(rows) * row_h + 44 + (14 * len(note_lines) + 12 if note_lines else 0)
    body: list[str] = []

    for t in ticks:
        x = x_of(t) + dx / 2
        body += [
            f'<text class="axis" x="{x:.1f}" y="{top - 12}" text-anchor="middle">{t.day} {t:%b}</text>',
            f'<line class="gridline" x1="{x:.1f}" x2="{x:.1f}" y1="{top - 6}" y2="{top + len(rows) * row_h - 8}"/>',
        ]

    for i, row in enumerate(rows):
        y = top + i * row_h + 20
        if row.tag:
            pw = max(30.0, text_w(row.tag, 10.5) + 12)
            body.append(f'<rect class="pill" x="18" y="{y - 1:.1f}" width="{pw:.1f}" height="17" rx="4"/>')
            body.append(f'<text class="pill-text mono" x="{18 + pw / 2:.1f}" y="{y + 11:.1f}" text-anchor="middle">{esc(row.tag)}</text>')
        body.append(f'<text class="row-label" x="{left - 12}" y="{y + 11}" text-anchor="end">{esc(row.label)}</text>')
        for b in row.bars:
            x0, x1 = x_of(b.start), x_of(b.end) + dx
            if b.kind == "commit":
                cx = (x0 + x1) / 2
                body.append(f'<rect class="k-commit" x="{cx - 9:.1f}" y="{y - 1}" width="18" height="16" rx="3"/>')
                if b.highlight:
                    body.append(f'<rect class="ring" x="{cx - 12:.1f}" y="{y - 4}" width="24" height="22" rx="5"/>')
                if len(b.label) <= 2:
                    body.append(f'<text class="commit-label mono" x="{cx:.1f}" y="{y + 10.5}" text-anchor="middle">{esc(b.label)}</text>')
                    continue
                x0 = x1 = cx
            else:
                body.append(f'<rect class="k-{b.kind}" x="{x0 + 1:.1f}" y="{y}" width="{max(6.0, x1 - x0 - 2):.1f}" height="14" rx="3"/>')
                if b.highlight:
                    body.append(f'<rect class="ring" x="{x0 - 2:.1f}" y="{y - 3}" width="{max(12.0, x1 - x0 + 4):.1f}" height="20" rx="5"/>')
            if b.label:
                tw = text_w(b.label)
                if x0 + 2 + tw <= right:
                    body.append(f'<text class="bar-label" x="{x0 + 2:.1f}" y="{y - 5}">{esc(b.label)}</text>')
                else:
                    body.append(f'<text class="bar-label" x="{min(x1, right):.1f}" y="{y - 5}" text-anchor="end">{esc(b.label)}</text>')

    y_bot = top + len(rows) * row_h + 14
    for k, line in enumerate(note_lines):
        body.append(f'<text class="note" x="20" y="{y_bot + k * 14}">{esc(line)}</text>')

    overrides = legend_overrides or {}
    kinds = [k for k in ("problem", "decoy", "partial", "neutral", "commit") if any(b.kind == k for r in rows for b in r.bars)]
    items = [(k, overrides.get(k, DEFAULT_LEGEND[k])) for k in kinds]
    if any(b.highlight for r in rows for b in r.bars):
        items.append(("ring", overrides.get("ring", DEFAULT_LEGEND["ring"])))
    height = y_bot + (14 * len(note_lines) + 22 if note_lines else 22)
    body += legend(items, height - 16)
    (OUT / f"{name}.svg").write_text(doc(height, title, body, subtitle=subtitle))


# ---------------------------------------------------------------- run grids


@dataclass(frozen=True)
class Cell:
    status: str  # ok | fail | cached | plain | accent-soft | warn-soft | fail-soft
    inside: str = ""
    below: str = ""
    ring: bool = False


@dataclass(frozen=True)
class GridRow:
    label: str
    cells: list[Cell | None]


@dataclass(frozen=True)
class Panel:
    heading: str
    rows: list[GridRow]
    verdict: str = ""


@dataclass(frozen=True)
class ColBand:
    start_col: int
    end_col: int  # inclusive
    label: str


def grid_chart(
    name: str,
    title: str,
    columns: list[str],
    panels: list[Panel],
    subtitle: str = "",
    note: str = "",
    legend_items: list[tuple[str, str]] | None = None,
    left: float = 165.0,
    bands: list[ColBand] | None = None,
    gap_after: int | None = None,
) -> None:
    right = W - 20.0
    gap_w = 24.0 if gap_after is not None else 0.0
    col_w = (right - left - gap_w) / len(columns)
    cell_w, cell_h = min(col_w - 8, 138), 28

    def col_x(j: int) -> float:
        return left + j * col_w + (gap_w if (gap_after is not None and j > gap_after) else 0.0)

    body: list[str] = []
    y = 70.0 if subtitle else 52.0

    # Optional column bands (e.g., B10 vs B10H)
    if bands:
        band_y = y - 2
        for b in bands:
            bx0 = col_x(b.start_col) + 2
            bx1 = col_x(b.end_col) + col_w - 2
            body.append(f'<rect class="band" x="{bx0:.1f}" y="{band_y:.1f}" width="{bx1 - bx0:.1f}" height="20" rx="4"/>')
            body.append(f'<text class="axis" x="{(bx0 + bx1) / 2:.1f}" y="{band_y + 14:.1f}" text-anchor="middle" font-weight="600">{esc(b.label)}</text>')
        y += 28

    for j, c in enumerate(columns):
        body.append(f'<text class="axis mono" x="{col_x(j) + col_w / 2:.1f}" y="{y + 6}" text-anchor="middle">{esc(c)}</text>')
    if gap_after is not None:
        gx = col_x(gap_after) + col_w + gap_w / 2
        body.append(f'<text class="axis" x="{gx:.1f}" y="{y + 6}" text-anchor="middle">...</text>')
    y += 22

    grid_top = y
    for p in panels:
        if p.heading:
            body.append(f'<text class="section-head" x="20" y="{y + 12}">{esc(p.heading)}</text>')
            y += 24
        for r in p.rows:
            lines = max([len(wrap(c.below, col_w - 4, 10.5)) for c in r.cells if c] + [0])
            body.append(f'<text class="row-label" x="{left - 12}" y="{y + cell_h / 2 + 4}" text-anchor="end">{esc(r.label)}</text>')
            for j, c in enumerate(r.cells):
                if c is None:
                    continue
                cx = col_x(j) + (col_w - cell_w) / 2
                body.append(f'<rect class="k-{c.status}" x="{cx:.1f}" y="{y}" width="{cell_w:.1f}" height="{cell_h}" rx="5"/>')
                if c.ring:
                    body.append(f'<rect class="ring" x="{cx - 3:.1f}" y="{y - 3}" width="{cell_w + 6:.1f}" height="{cell_h + 6}" rx="7"/>')
                if c.inside:
                    cls = "cell-text-inv" if c.status == "fail" else "cell-text"
                    body.append(f'<text class="{cls}" x="{cx + cell_w / 2:.1f}" y="{y + cell_h / 2 + 4}" text-anchor="middle">{esc(c.inside)}</text>')
                for k, line in enumerate(wrap(c.below, col_w - 4, 10.5)):
                    body.append(f'<text class="note" x="{cx + cell_w / 2:.1f}" y="{y + cell_h + 14 + k * 13}" text-anchor="middle">{esc(line)}</text>')
            y += cell_h + 14 + lines * 13
        if p.verdict:
            body.append(f'<text class="row-label" x="{left}" y="{y + 3}" font-weight="600">{esc(p.verdict)}</text>')
            y += 22
        y += 6

    if gap_after is not None:
        gx = col_x(gap_after) + col_w + gap_w / 2
        body.append(f'<line class="dashed" x1="{gx:.1f}" x2="{gx:.1f}" y1="{grid_top - 4}" y2="{y - 8}"/>')

    if note:
        note_lines = wrap(note, W - 40, 11)
        for k, line in enumerate(note_lines):
            body.append(f'<text class="note" x="20" y="{y + 6 + k * 14}">{esc(line)}</text>')
        y += 14 * len(note_lines) + 8

    items = legend_items or [("ok", "completed"), ("fail", "failed"), ("ring", "what the grader checks")]
    height = y + 36
    body += legend(items, height - 15)
    (OUT / f"{name}.svg").write_text(doc(height, title, body, subtitle=subtitle))


# ---------------------------------------------------------------- flows


@dataclass(frozen=True)
class Box:
    name: str
    text: str = ""
    kind: str = ""  # "" | hot | good | warn | soft


@dataclass(frozen=True)
class Lane:
    heading: str
    stages: list[Box | list[Box]]


def flow_chart(
    name: str,
    title: str,
    lanes: list[Lane],
    subtitle: str = "",
    note: str = "",
    legend_items: list[tuple[str, str]] | None = None,
    connect_lanes: bool = False,
) -> None:
    body: list[str] = []
    y = 68.0 if subtitle else 50.0
    lane_centers: list[tuple[float, float]] = []

    for idx, lane in enumerate(lanes):
        if lane.heading:
            body.append(f'<text class="section-head" x="20" y="{y + 12}">{esc(lane.heading)}</text>')
            y += 22
        n, gap = len(lane.stages), 28.0
        bw = (W - 40 - gap * (n - 1)) / n
        cols = [s if isinstance(s, list) else [s] for s in lane.stages]
        heights = [[44 + 14 * len(wrap(b.text, bw - 20)) for b in col] for col in cols]
        tallest = max(h[0] for h in heights if len(h) == 1) if any(len(h) == 1 for h in heights) else 0
        heights = [[tallest] if len(h) == 1 else h for h in heights]
        lane_h = max(sum(h) + 10 * (len(h) - 1) for h in heights)
        lane_top = y

        for j, col in enumerate(cols):
            x = 20 + j * (bw + gap)
            stack_h = sum(heights[j]) + 10 * (len(col) - 1)
            by = y + (lane_h - stack_h) / 2
            for b, bh in zip(col, heights[j]):
                cls = {"hot": "box-hot", "good": "box-good", "warn": "box-warn", "soft": "box-soft"}.get(b.kind, "box")
                name_cls = {"hot": "box-name-hot", "warn": "box-name-warn"}.get(b.kind, "box-name")
                body.append(f'<rect class="{cls}" x="{x:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh}" rx="8"/>')
                body.append(f'<text class="{name_cls} mono" x="{x + 10:.1f}" y="{by + 20:.1f}">{esc(b.name)}</text>')
                for k, line in enumerate(wrap(b.text, bw - 20)):
                    body.append(f'<text class="box-text" x="{x + 10:.1f}" y="{by + 37 + k * 14:.1f}">{esc(line)}</text>')
                if j + 1 < n:
                    nxt_col = cols[j + 1]
                    nxt_hs = heights[j + 1]
                    nxt_stack_h = sum(nxt_hs) + 10 * (len(nxt_col) - 1)
                    nxt_by = y + (lane_h - nxt_stack_h) / 2
                    if len(col) == 1 and len(nxt_col) > 1:
                        # fan out to each stacked box in next column
                        for nb, nbh in zip(nxt_col, nxt_hs):
                            acls = "arrow-hot" if nb.kind == "hot" else "arrow-accent" if nb.kind == "good" else "arrow"
                            ny = nxt_by + nbh / 2
                            body.append(
                                f'<path class="{acls}" d="M{x + bw + 2:.1f} {by + bh / 2:.1f} '
                                f'C{x + bw + gap / 2:.1f} {by + bh / 2:.1f} {x + bw + gap / 2:.1f} {ny:.1f} {x + bw + gap - 3:.1f} {ny:.1f}"/>'
                            )
                            nxt_by += nbh + 10
                    elif b.kind != "hot":
                        ny = y + lane_h / 2
                        acls = "arrow-accent" if b.kind == "good" else "arrow"
                        body.append(
                            f'<path class="{acls}" d="M{x + bw + 2:.1f} {by + bh / 2:.1f} '
                            f'C{x + bw + gap / 2:.1f} {by + bh / 2:.1f} {x + bw + gap / 2:.1f} {ny:.1f} {x + bw + gap - 3:.1f} {ny:.1f}"/>'
                        )
                by += bh + 10

        lane_centers.append((lane_top, lane_top + lane_h))
        if connect_lanes and idx + 1 < len(lanes):
            # Subtle downward connector from lane 1 to lane 2
            mid_x = W / 2
            body.append(f'<path class="arrow-accent" d="M{mid_x:.1f} {lane_top + lane_h + 3:.1f} L{mid_x:.1f} {lane_top + lane_h + 24:.1f}"/>')
            body.append(f'<text class="axis" x="{mid_x + 10:.1f}" y="{lane_top + lane_h + 18:.1f}">container image starts every attempt</text>')
            y += lane_h + 30
        else:
            y += lane_h + 22

    if note:
        note_lines = wrap(note, W - 40, 11)
        for k, line in enumerate(note_lines):
            body.append(f'<text class="note" x="20" y="{y + 2 + k * 14}">{esc(line)}</text>')
        y += 14 * len(note_lines) + 8

    if legend_items:
        height = y + 34
        body += legend(legend_items, height - 15)
    else:
        height = y + 14
    (OUT / f"{name}.svg").write_text(doc(height, title, body, subtitle=subtitle))


# ---------------------------------------------------------------- custom diagrams


def zb_overview_chart() -> None:
    """1-glance map of ZenML Bench: 5 capability groups (18 tasks) + 3 conditions + generated families."""
    body: list[str] = []
    y = 70.0
    groups = [
        ("Author & migrate", "3 tasks", ["b2-script-to-pipeline", "b9-modernise-old-api", "b5-custom-materializer"],
         "Turn scripts into typed pipelines, upgrade 0.4x APIs, write materializers."),
        ("Caching", "2 tasks", ["b3-stale-cache", "b4-nondeterministic-step"],
         "Invalidate on file contents (not path strings) and keep random steps fresh."),
        ("History & lineage", "4 tasks", ["b10-why-did-it-fail", "b10h (hard)", "b14-artifact-retrieval", "b14h (hard)"],
         "Diagnose real failures past decoys; trace lineage with supersession rules."),
        ("Models & config", "4 tasks", ["b6-model-promotion", "b7-kubernetes-settings", "b11-stack-registration", "b1-source-root-repair"],
         "Promote stages safely, configure K8s pods, register stacks, fix .zen roots."),
        ("Research loops", "5 tasks", ["r1-improve-within-budget", "r2-screen-then-confirm", "r1-clock", "r1-bare", "r1-bare-clock"],
         "Iterative ML under a 12-run or 25-min budget, plus no-framework twins."),
    ]
    cw = (W - 40 - 12 * 4) / 5
    card_h = 226.0
    for i, (heading, count, tasks, desc) in enumerate(groups):
        x = 20 + i * (cw + 12)
        body.append(f'<rect class="box" x="{x:.1f}" y="{y:.1f}" width="{cw:.1f}" height="{card_h:.1f}" rx="8"/>')
        body.append(f'<text class="box-name" x="{x + 10:.1f}" y="{y + 20:.1f}">{esc(heading)}</text>')
        body.append(f'<text class="axis" x="{x + 10:.1f}" y="{y + 34:.1f}">{esc(count)}</text>')
        ty = y + 44
        for t in tasks:
            is_h = "(hard)" in t
            pcls = "pill-hot" if is_h else "pill"
            tcls = "pill-hot-text" if is_h else "pill-text"
            body.append(f'<rect class="{pcls}" x="{x + 8:.1f}" y="{ty:.1f}" width="{cw - 16:.1f}" height="18" rx="4"/>')
            body.append(f'<text class="{tcls} mono" x="{x + 13:.1f}" y="{ty + 12.5:.1f}" font-size="9.5">{esc(t)}</text>')
            ty += 22
        dy = y + 166
        for k, line in enumerate(wrap(desc, cw - 20, 10.5)):
            body.append(f'<text class="note" x="{x + 10:.1f}" y="{dy + k * 13:.1f}">{esc(line)}</text>')

    # Bottom strip: 3 conditions + 2 generated families
    by = y + card_h + 16
    left_w = 540.0
    right_w = W - 40 - left_w - 14
    body.append(f'<rect class="box-soft" x="20" y="{by:.1f}" width="{left_w:.1f}" height="62" rx="8"/>')
    body.append(f'<text class="box-name" x="32" y="{by + 20:.1f}">Three evaluation conditions (same tasks, same graders)</text>')
    body.append(f'<text class="box-text" x="32" y="{by + 38:.1f}">bare: container + offline docs  ·  skill: + pinned ZenML skills  ·  mcp: + ZenML MCP server</text>')
    body.append(f'<text class="note" x="32" y="{by + 53:.1f}">Lets you measure whether docs, skills, or MCP tools actually move pass rates.</text>')

    rx = 20 + left_w + 14
    body.append(f'<rect class="box" x="{rx:.1f}" y="{by:.1f}" width="{right_w:.1f}" height="62" rx="8"/>')
    body.append(f'<text class="box-name" x="{rx + 12:.1f}" y="{by + 20:.1f}">Generated families (for RL training)</text>')
    body.append(f'<text class="box-text" x="{rx + 12:.1f}" y="{by + 38:.1f}">b10 &amp; b3 generators vary faults, names &amp; data</text>')
    body.append(f'<text class="note" x="{rx + 12:.1f}" y="{by + 53:.1f}">Seeds 0–4 committed as held-out; 1000+ for training.</text>')

    height = by + 78
    (OUT / "zb-overview.svg").write_text(
        doc(height, "ZenML Bench at a glance: 18 tasks, 13 projects, 3 conditions", body,
            subtitle="Every task grades what ZenML actually recorded in its store — never what the agent claims in chat.")
    )


def zb_how_a_run_works_chart() -> None:
    """Accurate diagram showing shared container store read/written by both agent and grader."""
    body: list[str] = []
    # Lane 1: Image build
    y1 = 68.0
    body.append(f'<text class="section-head" x="20" y="{y1 + 12}">1. Image build (once per task, offline)</text>')
    y1 += 20
    bw, gap, bh = (W - 40 - 28 * 2) / 3, 28.0, 70.0
    l1 = [
        ("base image", "Python 3.14, ZenML 0.96.4, agent CLIs, offline docs, ZenML MCP server"),
        ("task image", "copies one of 13 shared projects to /app and runs zenml init"),
        ("setup_store.sh", "optional: registers stacks, or runs the real pipeline to seed history"),
    ]
    for j, (nm, tx) in enumerate(l1):
        x = 20 + j * (bw + gap)
        body.append(f'<rect class="box" x="{x:.1f}" y="{y1:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="8"/>')
        body.append(f'<text class="box-name mono" x="{x + 10:.1f}" y="{y1 + 20:.1f}">{esc(nm)}</text>')
        for k, line in enumerate(wrap(tx, bw - 20)):
            body.append(f'<text class="box-text" x="{x + 10:.1f}" y="{y1 + 37 + k * 14:.1f}">{esc(line)}</text>')
        if j < 2:
            body.append(f'<path class="arrow" d="M{x + bw + 2:.1f} {y1 + bh / 2:.1f} L{x + bw + gap - 3:.1f} {y1 + bh / 2:.1f}"/>')

    # Connector down
    mid = W / 2
    body.append(f'<path class="arrow-accent" d="M{mid:.1f} {y1 + bh + 3:.1f} L{mid:.1f} {y1 + bh + 25:.1f}"/>')
    body.append(f'<text class="axis" x="{mid + 10:.1f}" y="{y1 + bh + 18:.1f}">fresh container for every attempt</text>')

    # Lane 2: One attempt with explicit shared store
    y2 = y1 + bh + 32
    body.append(f'<text class="section-head" x="20" y="{y2 + 12}">2. One attempt inside the container</text>')
    y2 += 22
    # 3 main boxes across top + store box below agent & grader
    ax, aw, ah = 20.0, 260.0, 82.0
    gx, gw, gh = 328.0, 340.0, 82.0
    rx, rw, rh = 716.0, W - 20 - 716.0, 82.0

    # Agent
    body.append(f'<rect class="box" x="{ax:.1f}" y="{y2:.1f}" width="{aw:.1f}" height="{ah:.1f}" rx="8"/>')
    body.append(f'<text class="box-name mono" x="{ax + 10:.1f}" y="{y2 + 20:.1f}">agent</text>')
    for k, line in enumerate(wrap("reads instruction.md, edits code & runs pipelines; 25–40 min; model API only", aw - 20)):
        body.append(f'<text class="box-text" x="{ax + 10:.1f}" y="{y2 + 37 + k * 14:.1f}">{esc(line)}</text>')

    # Grader
    body.append(f'<rect class="box-good" x="{gx:.1f}" y="{y2:.1f}" width="{gw:.1f}" height="{gh:.1f}" rx="8"/>')
    body.append(f'<text class="box-name mono" x="{gx + 10:.1f}" y="{y2 + 20:.1f}">hidden grader (offline)</text>')
    for k, line in enumerate(wrap("re-runs the agent's entrypoint on unseen fixtures, verifies run genuineness & reads ZenML store", gw - 20)):
        body.append(f'<text class="box-text" x="{gx + 10:.1f}" y="{y2 + 37 + k * 14:.1f}">{esc(line)}</text>')

    # Reward
    body.append(f'<rect class="box-good" x="{rx:.1f}" y="{y2:.1f}" width="{rw:.1f}" height="{rh:.1f}" rx="8"/>')
    body.append(f'<text class="box-name mono" x="{rx + 10:.1f}" y="{y2 + 20:.1f}">reward</text>')
    for k, line in enumerate(wrap("1 (all checks pass) or 0 (any check or integrity rule fails)", rw - 20)):
        body.append(f'<text class="box-text" x="{rx + 10:.1f}" y="{y2 + 37 + k * 14:.1f}">{esc(line)}</text>')

    # Arrows: agent -> grader ("finishes"), grader -> reward
    body.append(f'<path class="arrow" d="M{ax + aw + 2:.1f} {y2 + ah / 2:.1f} L{gx - 3:.1f} {y2 + ah / 2:.1f}"/>')
    body.append(f'<text class="axis" x="{ax + aw + 24:.1f}" y="{y2 + ah / 2 - 7:.1f}" text-anchor="middle">done</text>')
    body.append(f'<path class="arrow-accent" d="M{gx + gw + 2:.1f} {y2 + ah / 2:.1f} L{rx - 3:.1f} {y2 + ah / 2:.1f}"/>')

    # Shared SQLite ZenML store underneath agent and grader
    sy = y2 + ah + 30
    sx, sw, sh = 95.0, 520.0, 56.0
    body.append(f'<rect class="box-soft" x="{sx:.1f}" y="{sy:.1f}" width="{sw:.1f}" height="{sh:.1f}" rx="8"/>')
    body.append(f'<text class="box-name mono" x="{sx + 12:.1f}" y="{sy + 21:.1f}">local ZenML SQLite store (inside container)</text>')
    body.append(f'<text class="box-text" x="{sx + 12:.1f}" y="{sy + 40:.1f}">runs, step statuses, cache keys, artifacts, model versions, compiled stack settings</text>')

    # Vertical arrows to/from store
    body.append(f'<path class="arrow" d="M{ax + aw * 0.65:.1f} {y2 + ah + 2:.1f} L{ax + aw * 0.65:.1f} {sy - 3:.1f}"/>')
    body.append(f'<text class="axis" x="{ax + aw * 0.65 - 8:.1f}" y="{y2 + ah + 19:.1f}" text-anchor="end">reads &amp; writes</text>')
    body.append(f'<path class="arrow-accent" d="M{gx + gw * 0.35:.1f} {y2 + ah + 2:.1f} L{gx + gw * 0.35:.1f} {sy - 3:.1f}"/>')
    body.append(f'<path class="arrow-accent" d="M{gx + gw * 0.55:.1f} {sy - 2:.1f} L{gx + gw * 0.55:.1f} {y2 + ah + 3:.1f}"/>')
    body.append(f'<text class="axis" x="{gx + gw * 0.55 + 8:.1f}" y="{y2 + ah + 19:.1f}">re-runs &amp; audits (assert_genuine_run)</text>')

    ly = sy + sh + 28
    body += legend([("box-good", "hidden grader boundary"), ("accent-soft", "shared store audited for tampering")], ly)
    (OUT / "zb-how-a-run-works.svg").write_text(
        doc(ly + 16, "How one ZenML Bench attempt runs", body,
            subtitle="Because the SQLite store lives in the container, graders re-run code on hidden data and verify every step is genuine.")
    )


def zb_b1_roots_chart() -> None:
    """Visual directory tree for B1 (analytics_workspace) showing .zen resolution."""
    body: list[str] = []
    y = 70.0
    left_w = 440.0
    right_x = 480.0
    right_w = W - 20 - right_x
    desc_col = 200.0  # fixed x-offset inside each panel so mono paths never collide with descriptions

    # Left: Before (broken)
    body.append(f'<rect class="box" x="20" y="{y:.1f}" width="{left_w:.1f}" height="218" rx="8"/>')
    body.append(f'<text class="section-head" x="34" y="{y + 22:.1f}">Starting state (broken)</text>')
    rows_before = [
        (0, "/app/", "", "plain"),
        (1, "analytics/", "no .zen -> daily can't import src/", "hot"),
        (2, "src/features.py", "shared helper", "muted"),
        (2, "pipelines/daily.py", "daily entrypoint", "muted"),
        (2, "jobs/backfill/.zen", "STRAY .zen -> run.load_history", "hot"),
        (2, "jobs/backfill/run.py", "stops walking at stray .zen", "muted"),
        (1, "legacy_reports/.zen", "neighbour + 1 run (DO NOT TOUCH)", "warn"),
    ]
    ry = y + 46
    for indent, path, desc, style in rows_before:
        px = 34 + indent * 14
        if style == "hot":
            body.append(f'<rect class="k-fail-soft" x="28" y="{ry - 13:.1f}" width="{left_w - 16:.1f}" height="20" rx="4"/>')
            body.append(f'<text class="mono" x="{px:.1f}" y="{ry:.1f}" font-size="11" font-weight="600" fill="var(--fail)">{esc(path)}</text>')
        elif style == "warn":
            body.append(f'<rect class="k-warn-soft" x="28" y="{ry - 13:.1f}" width="{left_w - 16:.1f}" height="20" rx="4"/>')
            body.append(f'<text class="mono" x="{px:.1f}" y="{ry:.1f}" font-size="11" font-weight="600" fill="var(--ink)">{esc(path)}</text>')
        else:
            body.append(f'<text class="mono" x="{px:.1f}" y="{ry:.1f}" font-size="11" font-weight="600">{esc(path)}</text>')
        if desc:
            body.append(f'<text class="note" x="{20 + desc_col:.1f}" y="{ry:.1f}">{esc(desc)}</text>')
        ry += 25

    # Right: After (fixed)
    body.append(f'<rect class="box-good" x="{right_x:.1f}" y="{y:.1f}" width="{right_w:.1f}" height="218" rx="8"/>')
    body.append(f'<text class="section-head" x="{right_x + 14:.1f}" y="{y + 22:.1f}">After fix (what the grader checks)</text>')
    rows_after = [
        (0, "/app/", "no .zen here (keeps neighbour safe)", "plain"),
        (1, "analytics/.zen", "single root for both entrypoints", "good"),
        (2, "src/features.py", "importable from /app/analytics", "muted"),
        (2, "pipelines/daily.py", "records pipelines.daily.*", "good"),
        (2, "jobs/backfill/", "stray .zen removed", "muted"),
        (2, "jobs/backfill/run.py", "records jobs.backfill.run.*", "good"),
        (1, "legacy_reports/.zen", "hashes, .zen & run untouched", "warn"),
    ]
    ry = y + 46
    for indent, path, desc, style in rows_after:
        px = right_x + 14 + indent * 14
        if style == "good":
            body.append(f'<rect class="pill" x="{right_x + 8:.1f}" y="{ry - 13:.1f}" width="{right_w - 16:.1f}" height="20" rx="4"/>')
            body.append(f'<text class="mono" x="{px:.1f}" y="{ry:.1f}" font-size="11" font-weight="600" fill="var(--accent)">{esc(path)}</text>')
        elif style == "warn":
            body.append(f'<rect class="k-warn-soft" x="{right_x + 8:.1f}" y="{ry - 13:.1f}" width="{right_w - 16:.1f}" height="20" rx="4"/>')
            body.append(f'<text class="mono" x="{px:.1f}" y="{ry:.1f}" font-size="11" font-weight="600" fill="var(--ink)">{esc(path)}</text>')
        else:
            body.append(f'<text class="mono" x="{px:.1f}" y="{ry:.1f}" font-size="11" font-weight="600">{esc(path)}</text>')
        if desc:
            body.append(f'<text class="note" x="{right_x + desc_col:.1f}" y="{ry:.1f}">{esc(desc)}</text>')
        ry += 25

    ny = y + 236
    body.append(f'<text class="note" x="20" y="{ny:.1f}">ZenML resolves step module paths relative to the nearest parent .zen directory. Hacking sys.path makes Python run, but leaves recorded sources wrong.</text>')
    (OUT / "zb-b1-roots.svg").write_text(
        doc(ny + 18, "B1 (analytics_workspace): why the stray .zen breaks step source paths", body,
            subtitle="Running `zenml init` at /app breaks the neighbour; keeping jobs/backfill/.zen leaves backfill paths truncated.")
    )


def zb_model_promotion_chart() -> None:
    """Shows the shared demand_forecaster registry + the B6 cache trap when production flips."""
    body: list[str] = []
    y = 70.0
    # Top row: train_forecaster -> Model Registry
    body.append(f'<text class="section-head" x="20" y="{y + 12}">Training (already run at image build)</text>')
    y += 20
    t_boxes = [
        ("train_forecaster", "runs twice: linear (v1, lower val_mae = better) & forest (v2, worse)", "box"),
        ("demand_forecaster", "v1 (better) · v2 (latest, worse) · stage: production", "box-soft"),
    ]
    w1, w2 = 430.0, 440.0
    body.append(f'<rect class="{t_boxes[0][2]}" x="20" y="{y:.1f}" width="{w1:.1f}" height="62" rx="8"/>')
    body.append(f'<text class="box-name mono" x="30" y="{y + 20:.1f}">{esc(t_boxes[0][0])}</text>')
    for k, line in enumerate(wrap(t_boxes[0][1], w1 - 20)):
        body.append(f'<text class="box-text" x="30" y="{y + 37 + k * 14:.1f}">{esc(line)}</text>')

    rx = 20 + w1 + 30
    body.append(f'<rect class="{t_boxes[1][2]}" x="{rx:.1f}" y="{y:.1f}" width="{w2:.1f}" height="62" rx="8"/>')
    body.append(f'<text class="box-name mono" x="{rx + 10:.1f}" y="{y + 20:.1f}">{esc(t_boxes[1][0])}</text>')
    for k, line in enumerate(wrap(t_boxes[1][1], w2 - 20)):
        body.append(f'<text class="box-text" x="{rx + 10:.1f}" y="{y + 37 + k * 14:.1f}">{esc(line)}</text>')
    body.append(f'<path class="arrow" d="M{20 + w1 + 2:.1f} {y + 31:.1f} L{rx - 3:.1f} {y + 31:.1f}"/>')

    # Down arrow from registry into batch_forecast (label placed to the LEFT so it never clips)
    y2 = y + 92
    ax_mid = rx + w2 / 2
    body.append(f'<path class="arrow-accent" d="M{ax_mid:.1f} {y + 64:.1f} L{ax_mid:.1f} {y2 + 17:.1f}"/>')
    body.append(f'<text class="axis" x="{ax_mid - 10:.1f}" y="{y + 82:.1f}" text-anchor="end">grader promotes the OTHER version, then re-runs on the SAME batch</text>')

    body.append(f'<text class="section-head" x="20" y="{y2 + 12}">Inference: batch_forecast(input_path) — the cache trap</text>')
    y2 += 22

    bx1, bw1 = 20.0, 210.0
    bx2, bw2 = 258.0, 255.0
    bx3, bw3 = 545.0, W - 20 - 545.0

    # load_batch
    body.append(f'<rect class="box" x="{bx1:.1f}" y="{y2 + 24:.1f}" width="{bw1:.1f}" height="74" rx="8"/>')
    body.append(f'<text class="box-name mono" x="{bx1 + 10:.1f}" y="{y2 + 44:.1f}">load_batch(path)</text>')
    for k, line in enumerate(wrap("reads the same hidden batch CSV on both grader runs", bw1 - 20)):
        body.append(f'<text class="box-text" x="{bx1 + 10:.1f}" y="{y2 + 61 + k * 14:.1f}">{esc(line)}</text>')

    # predict
    body.append(f'<rect class="box-hot" x="{bx2:.1f}" y="{y2 + 24:.1f}" width="{bw2:.1f}" height="74" rx="8"/>')
    body.append(f'<text class="box-name-hot mono" x="{bx2 + 10:.1f}" y="{y2 + 44:.1f}">predict(batch)</text>')
    for k, line in enumerate(wrap("loads Model(version=\"production\") inside; stage is NOT in ZenML's cache key", bw2 - 20)):
        body.append(f'<text class="box-text" x="{bx2 + 10:.1f}" y="{y2 + 61 + k * 14:.1f}">{esc(line)}</text>')

    body.append(f'<path class="arrow" d="M{bx1 + bw1 + 2:.1f} {y2 + 61:.1f} L{bx2 - 3:.1f} {y2 + 61:.1f}"/>')

    # Branch: naive vs fixed
    body.append(f'<rect class="box-hot" x="{bx3:.1f}" y="{y2:.1f}" width="{bw3:.1f}" height="56" rx="8"/>')
    body.append(f'<text class="box-name-hot mono" x="{bx3 + 10:.1f}" y="{y2 + 19:.1f}">naive fix: stage only (reward 0)</text>')
    body.append(f'<text class="box-text" x="{bx3 + 10:.1f}" y="{y2 + 37:.1f}">predict hits cache -> linked to new version, old predictions</text>')

    by_good = y2 + 66
    body.append(f'<rect class="box-good" x="{bx3:.1f}" y="{by_good:.1f}" width="{bw3:.1f}" height="56" rx="8"/>')
    body.append(f'<text class="box-name mono" x="{bx3 + 10:.1f}" y="{by_good + 19:.1f}">working fix: pass version / uncache (reward 1)</text>')
    body.append(f'<text class="box-text" x="{bx3 + 10:.1f}" y="{by_good + 37:.1f}">predictions &amp; model link both follow the promoted version</text>')

    body.append(f'<path class="arrow-hot" d="M{bx2 + bw2 + 2:.1f} {y2 + 61:.1f} C{bx2 + bw2 + 16:.1f} {y2 + 61:.1f} {bx3 - 16:.1f} {y2 + 28:.1f} {bx3 - 3:.1f} {y2 + 28:.1f}"/>')
    body.append(f'<path class="arrow-accent" d="M{bx2 + bw2 + 2:.1f} {y2 + 61:.1f} C{bx2 + bw2 + 16:.1f} {y2 + 61:.1f} {bx3 - 16:.1f} {by_good + 28:.1f} {bx3 - 3:.1f} {by_good + 28:.1f}"/>')

    height = by_good + 72
    (OUT / "zb-model-promotion.svg").write_text(
        doc(height, "B6 (model_promotion): why switching to Model(version=\"production\") isn't enough", body,
            subtitle="ZenML caches steps on code + inputs; changing which version holds `production` does not invalidate `predict`.")
    )


def kb_overview_chart() -> None:
    """1-glance 5-worlds x 5-families matrix of all 37 Kitaru Bench tasks."""
    body: list[str] = []
    families = ["Checks (8)", "Diagnosis (10)", "Import (7)", "Replay (8)", "Setup (4)"]
    worlds = [
        ("storefront", "Larkspur Goods · ~3k runs", [
            ["c1", "c1h*", "c2", "c3", "c4", "c5", "c6", "c7*"],
            ["d6", "d7", "d8", "d8h*", "d9"],
            [], [], [],
        ]),
        ("clinic", "Fernhill Vets · 3,211 runs", [
            [], ["d1", "d2", "d3", "d4", "d5"], [], [], [],
        ]),
        ("exports", "Tidewater · external logs", [
            [], [], ["i1", "i2", "i3", "i3h*", "i4", "i4h*", "i5"], [], [],
        ]),
        ("helpdesk-live", "Live PydanticAI · 260 runs", [
            [], [], [], ["f1", "f2", "f3", "f4"], [],
        ]),
        ("helpdesk-services", "Live + slow API · 420 runs", [
            [], [], [], ["f5", "f6", "f7", "f8"], ["o1", "o2", "o3", "o4"],
        ]),
    ]

    left = 185.0
    col_w = (W - 20 - left) / len(families)
    y = 74.0

    for j, f in enumerate(families):
        body.append(f'<text class="section-head" x="{left + j * col_w + col_w / 2:.1f}" y="{y:.1f}" text-anchor="middle">{esc(f)}</text>')
    y += 14

    row_h = 54.0
    for i, (wname, wsub, cells) in enumerate(worlds):
        ry = y + i * (row_h + 6)
        body.append(f'<rect class="band" x="20" y="{ry:.1f}" width="{W - 40:.1f}" height="{row_h:.1f}" rx="6"/>')
        body.append(f'<text class="box-name mono" x="30" y="{ry + 22:.1f}">{esc(wname)}</text>')
        body.append(f'<text class="note" x="30" y="{ry + 39:.1f}">{esc(wsub)}</text>')
        for j, tasks in enumerate(cells):
            cx = left + j * col_w + 6
            cw = col_w - 12
            if not tasks:
                body.append(f'<text class="note" x="{cx + cw / 2:.1f}" y="{ry + row_h / 2 + 4:.1f}" text-anchor="middle">—</text>')
                continue
            # Lay out task pills wrapping neatly inside cw
            px, py = cx, ry + 8
            for t in tasks:
                is_hard = t.endswith("*")
                label = t.rstrip("*")
                pw = max(28.0, text_w(label, 10.5) + 10)
                if px + pw > cx + cw + 1:
                    px = cx
                    py += 20
                pcls = "pill-hot" if is_hard else "pill"
                tcls = "pill-hot-text" if is_hard else "pill-text"
                body.append(f'<rect class="{pcls}" x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="17" rx="4"/>')
                body.append(f'<text class="{tcls} mono" x="{px + pw / 2:.1f}" y="{py + 12:.1f}" text-anchor="middle">{esc(label)}</text>')
                px += pw + 4

    ly = y + len(worlds) * (row_h + 6) + 18
    body += [
        f'<rect class="pill" x="20" y="{ly - 12:.1f}" width="16" height="14" rx="3"/>',
        f'<text class="legend" x="42" y="{ly - 1:.1f}">standard task (32)</text>',
        f'<rect class="pill-hot" x="175" y="{ly - 12:.1f}" width="16" height="14" rx="3"/>',
        f'<text class="legend" x="197" y="{ly - 1:.1f}">harder variant added after large models saturated the original (5: c1h, c7, d8h, i3h, i4h)</text>',
    ]
    (OUT / "kb-overview.svg").write_text(
        doc(ly + 16, "Kitaru Bench at a glance: 5 worlds × 5 task families (37 tasks)", body,
            subtitle="Each world is a fictional company image reused by a group of tasks; families reflect the operational job.")
    )


def kb_how_a_run_works_chart() -> None:
    """Shows image build -> attempt with explicit user 'agent' (HTTP) vs root/'grader' isolation."""
    body: list[str] = []
    y1 = 68.0
    body.append(f'<text class="section-head" x="20" y="{y1 + 12}">1. Image build (once per task)</text>')
    y1 += 20
    bw, gap, bh = (W - 40 - 28 * 2) / 3, 28.0, 68.0
    l1 = [
        ("base image", "Kitaru 0.27.7, PostgreSQL, agent CLIs, plugin wheels, offline docs"),
        ("world section", "load.py imports or records the seeded history story.py planned"),
        ("task section", "optional setup/: pre-registered versions, cohorts, damaged imports"),
    ]
    for j, (nm, tx) in enumerate(l1):
        x = 20 + j * (bw + gap)
        body.append(f'<rect class="box" x="{x:.1f}" y="{y1:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="8"/>')
        body.append(f'<text class="box-name mono" x="{x + 10:.1f}" y="{y1 + 20:.1f}">{esc(nm)}</text>')
        for k, line in enumerate(wrap(tx, bw - 20)):
            body.append(f'<text class="box-text" x="{x + 10:.1f}" y="{y1 + 37 + k * 14:.1f}">{esc(line)}</text>')
        if j < 2:
            body.append(f'<path class="arrow" d="M{x + bw + 2:.1f} {y1 + bh / 2:.1f} L{x + bw + gap - 3:.1f} {y1 + bh / 2:.1f}"/>')

    mid = W / 2
    body.append(f'<path class="arrow-accent" d="M{mid:.1f} {y1 + bh + 3:.1f} L{mid:.1f} {y1 + bh + 25:.1f}"/>')
    body.append(f'<text class="axis" x="{mid + 10:.1f}" y="{y1 + bh + 18:.1f}">runs on Modal (network allow-list: model APIs only)</text>')

    y2 = y1 + bh + 32
    body.append(f'<text class="section-head" x="20" y="{y2 + 12}">2. One attempt (three Linux users enforce isolation)</text>')
    y2 += 22
    stages = [
        ("start.sh (root)", "healthcheck starts Postgres (fresh password), Kitaru server & bench-worker", "box"),
        ("agent (user: agent)", "HTTP only (127.0.0.1:8000); 30 min (45m on F7), 2 CPUs; cannot read DB or /tests", "box"),
        ("grader (root + 'grader')", "locks /tests, kills agent procs, runs agent's registered code as user 'grader'", "box-good"),
        ("reward", "1 or 0 from Kitaru records, root-only service logs & hidden inputs", "box-good"),
    ]
    n, g2 = len(stages), 22.0
    w2 = (W - 40 - g2 * (n - 1)) / n
    h2 = 96.0
    for j, (nm, tx, cls) in enumerate(stages):
        x = 20 + j * (w2 + g2)
        body.append(f'<rect class="{cls}" x="{x:.1f}" y="{y2:.1f}" width="{w2:.1f}" height="{h2:.1f}" rx="8"/>')
        body.append(f'<text class="box-name mono" x="{x + 10:.1f}" y="{y2 + 20:.1f}">{esc(nm)}</text>')
        for k, line in enumerate(wrap(tx, w2 - 20)):
            body.append(f'<text class="box-text" x="{x + 10:.1f}" y="{y2 + 37 + k * 14:.1f}">{esc(line)}</text>')
        if j + 1 < n:
            body.append(f'<path class="arrow" d="M{x + w2 + 2:.1f} {y2 + h2 / 2:.1f} L{x + w2 + g2 - 3:.1f} {y2 + h2 / 2:.1f}"/>')

    ly = y2 + h2 + 26
    body += legend([("box-good", "privileged grading phase (isolated from agent code)")], ly)
    (OUT / "kb-how-a-run-works.svg").write_text(
        doc(ly + 16, "How one Kitaru Bench attempt runs", body,
            subtitle="Everything runs inside one container; Linux users and root-only logs prevent the agent from reading answers or faking payments.")
    )


def kb_exports_langfuse_chart() -> None:
    """Visualizes I2: Langfuse sessionId (widget visit) vs metadata.ticket.id."""
    body: list[str] = []
    y = 70.0
    # Top row: raw Langfuse traces
    body.append(f'<text class="section-head" x="20" y="{y + 12}">Raw Langfuse export (1 trace per turn; sessionId = browser widget visit)</text>')
    y += 22
    traces = [
        ("trace 1", "visit-A · ticket #101", "accent-soft"),
        ("trace 2", "visit-A · ticket #102", "warn-soft"),
        ("trace 3", "visit-B · ticket #102", "warn-soft"),
        ("trace 4", "visit-C · monitor probe", "plain"),
    ]
    tw = (W - 40 - 16 * 3) / 4
    for j, (tname, tmeta, tcls) in enumerate(traces):
        x = 20 + j * (tw + 16)
        body.append(f'<rect class="k-{tcls}" x="{x:.1f}" y="{y:.1f}" width="{tw:.1f}" height="44" rx="6"/>')
        body.append(f'<text class="cell-text mono" x="{x + tw / 2:.1f}" y="{y + 18:.1f}" text-anchor="middle">{esc(tname)}</text>')
        body.append(f'<text class="note" x="{x + tw / 2:.1f}" y="{y + 34:.1f}" text-anchor="middle">{esc(tmeta)}</text>')

    # Two comparison boxes below
    y2 = y + 72
    bw = (W - 40 - 24) / 2
    # Left: Default (wrong)
    body.append(f'<rect class="box-hot" x="20" y="{y2:.1f}" width="{bw:.1f}" height="102" rx="8"/>')
    body.append(f'<text class="box-name-hot" x="32" y="{y2 + 21:.1f}">Default import: groups by sessionId (reward 0)</text>')
    body.append(f'<text class="box-text mono" x="32" y="{y2 + 44:.1f}">visit-A  -&gt;  [trace 1 (#101) + trace 2 (#102)]  mixed!</text>')
    body.append(f'<text class="box-text mono" x="32" y="{y2 + 64:.1f}">visit-B  -&gt;  [trace 3 (#102)]                  split!</text>')
    body.append(f'<text class="box-text mono" x="32" y="{y2 + 84:.1f}">visit-C  -&gt;  [trace 4 (probe)]                 junk!</text>')

    # Right: Fixed (right)
    rx = 20 + bw + 24
    body.append(f'<rect class="box-good" x="{rx:.1f}" y="{y2:.1f}" width="{bw:.1f}" height="102" rx="8"/>')
    body.append(f'<text class="box-name" x="{rx + 12:.1f}" y="{y2 + 21:.1f}">I2 script: groups by metadata.ticket.id (reward 1)</text>')
    body.append(f'<text class="box-text mono" x="{rx + 12:.1f}" y="{y2 + 44:.1f}">ticket #101  -&gt;  [trace 1]</text>')
    body.append(f'<text class="box-text mono" x="{rx + 12:.1f}" y="{y2 + 64:.1f}">ticket #102  -&gt;  [trace 2 + trace 3]  reunited</text>')
    body.append(f'<text class="box-text mono" x="{rx + 12:.1f}" y="{y2 + 84:.1f}">probe        -&gt;  dropped</text>')

    # Arrows from raw row down to both boxes
    body.append(f'<path class="arrow-hot" d="M{20 + bw / 2:.1f} {y + 48:.1f} L{20 + bw / 2:.1f} {y2 - 3:.1f}"/>')
    body.append(f'<path class="arrow-accent" d="M{rx + bw / 2:.1f} {y + 48:.1f} L{rx + bw / 2:.1f} {y2 - 3:.1f}"/>')

    height = y2 + 118
    (OUT / "kb-exports-langfuse.svg").write_text(
        doc(height, "I2 (exports): why Langfuse sessionId splits and mixes support tickets", body,
            subtitle="30% of tickets share a chat-widget visit, and returning customers open a new visit for the same ticket.")
    )


def kb_exports_nightly_chart() -> None:
    """Sliding 2-day window diagram showing WHY v2 creates 96 strays and 48 stray-only tickets."""
    body: list[str] = []
    days = ["Day 4", "Day 5", "Day 6", "Day 7", "Day 8"]
    left = 260.0
    col_w = (W - 24 - left) / len(days)
    y = 74.0

    for j, day in enumerate(days):
        cx = left + j * col_w + col_w / 2
        body.append(f'<text class="axis mono" x="{cx:.1f}" y="{y:.1f}" text-anchor="middle">{esc(day)}</text>')
        body.append(f'<line class="gridline" x1="{left + j * col_w:.1f}" x2="{left + j * col_w:.1f}" y1="{y + 8:.1f}" y2="{y + 236:.1f}"/>')
    y += 18

    # Rows: each nightly import covering [d-1, d], with clean caption right beneath each bar
    rows = [
        ("Night 5 (v1: tidewater-support)", 0, 1, "ok", "d4 skipped · d5 imported", "reviewed-week-31 cohort pinned to these IDs"),
        ("5 Aug commit breaks source ID", None, None, "commit", "", "source becomes filename: support-2026-08-06, ...-07"),
        ("Night 6 (v2: filename source)", 1, 2, "fail", "d5 duplicated · d6 STRAY ONLY", "48 strays (24 dupes of d5 + 24 new d6)"),
        ("Night 7 (v2: filename source)", 2, 3, "fail", "d6 duplicated · d7 STRAY ONLY", "48 strays (24 dupes of d6 + 24 new d7)"),
        ("Night 8 (grader runs your fix ×2)", 3, 4, "accent-soft", "d7 skipped · d8 imported once", "2nd run must create 0 new sessions"),
    ]
    for label, s_idx, e_idx, kind, bar_txt, sub in rows:
        body.append(f'<text class="row-label" x="{left - 12:.1f}" y="{y + 16:.1f}" text-anchor="end">{esc(label)}</text>')
        if kind == "commit":
            cx = left + 2 * col_w
            body.append(f'<line class="dashed" x1="{left:.1f}" x2="{W - 24:.1f}" y1="{y + 12:.1f}" y2="{y + 12:.1f}"/>')
            body.append(f'<rect class="k-commit" x="{cx - 7:.1f}" y="{y + 5:.1f}" width="14" height="14" rx="3"/>')
            body.append(f'<text class="note" x="{cx + 14:.1f}" y="{y + 16:.1f}">{esc(sub)}</text>')
            y += 32
            continue
        assert s_idx is not None and e_idx is not None
        x0 = left + s_idx * col_w + 4
        w = (e_idx - s_idx + 1) * col_w - 8
        body.append(f'<rect class="k-{kind}" x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="24" rx="5"/>')
        tcls = "cell-text-inv" if kind == "fail" else "cell-text"
        body.append(f'<text class="{tcls}" x="{x0 + w / 2:.1f}" y="{y + 16:.1f}" text-anchor="middle">{esc(bar_txt)}</text>')
        body.append(f'<text class="note" x="{x0 + w / 2:.1f}" y="{y + 38:.1f}" text-anchor="middle">{esc(sub)}</text>')
        y += 50

    ny = y + 12
    body.append(f'<text class="note" x="20" y="{ny:.1f}">Why naive fixes fail: wiping the store destroys the reviewed-week-31 sessions; deleting all strays without re-importing loses days 6 and 7.</text>')
    ly = ny + 26
    body += legend([("ok", "correct identity (keep)"), ("fail", "stray identity (96 sessions)"), ("accent-soft", "grader verification")], ly)
    (OUT / "kb-exports-nightly.svg").write_text(
        doc(ly + 16, "I4 / I4h (exports): how the 2-day sliding window creates strays and stray-only tickets", body,
            subtitle="Every nightly file holds yesterday + today. Changing the source ID on 5 Aug broke deduplication for nights 6 and 7.")
    )


def kb_helpdesk_services_chart() -> None:
    """Service topology + F6 concurrency trap for helpdesk-services."""
    body: list[str] = []
    y = 70.0
    # Top: topology
    ax, aw, ah = 20.0, 270.0, 96.0
    body.append(f'<rect class="box" x="{ax:.1f}" y="{y + 12:.1f}" width="{aw:.1f}" height="{ah:.1f}" rx="8"/>')
    body.append(f'<text class="box-name mono" x="{ax + 12:.1f}" y="{y + 33:.1f}">helpdesk-agent (v2.0.0)</text>')
    for k, line in enumerate(wrap("Real PydanticAI agent + deterministic planner. 420 recorded requests, 7 places where it asks twice.", aw - 24)):
        body.append(f'<text class="box-text" x="{ax + 12:.1f}" y="{y + 51 + k * 14:.1f}">{esc(line)}</text>')

    sx = 340.0
    sw = W - 20 - sx
    # Order service
    body.append(f'<rect class="box-warn" x="{sx:.1f}" y="{y:.1f}" width="{sw:.1f}" height="56" rx="8"/>')
    body.append(f'<text class="box-name-warn mono" x="{sx + 12:.1f}" y="{y + 20:.1f}">order service (:8092) — slow &amp; rate-limited</text>')
    body.append(f'<text class="box-text" x="{sx + 12:.1f}" y="{y + 39:.1f}">0.25 s per call · max 4 concurrent (5th gets HTTP 429) · root-only request log (F5, F6)</text>')

    # Finance service
    fy = y + 66
    body.append(f'<rect class="box-hot" x="{sx:.1f}" y="{fy:.1f}" width="{sw:.1f}" height="56" rx="8"/>')
    body.append(f'<text class="box-name-hot mono" x="{sx + 12:.1f}" y="{fy + 20:.1f}">finance service (:8091) — real side effects</text>')
    body.append(f'<text class="box-text" x="{sx + 12:.1f}" y="{fy + 39:.1f}">issue_refund &amp; escalate_to_human append to a root-only ledger; 1 extra row = reward 0</text>')

    body.append(f'<path class="arrow" d="M{ax + aw + 2:.1f} {y + 60:.1f} C{ax + aw + 25:.1f} {y + 60:.1f} {sx - 25:.1f} {y + 28:.1f} {sx - 3:.1f} {y + 28:.1f}"/>')
    body.append(f'<path class="arrow-hot" d="M{ax + aw + 2:.1f} {y + 60:.1f} C{ax + aw + 25:.1f} {y + 60:.1f} {sx - 25:.1f} {fy + 28:.1f} {sx - 3:.1f} {fy + 28:.1f}"/>')

    # Bottom strip: F6 concurrency trap
    y2 = fy + 78
    body.append(f'<text class="section-head" x="20" y="{y2 + 12}">Example trap (F6): why unbounded asyncio.gather() passes locally and fails hidden grading</text>')
    y2 += 20
    cw = (W - 40 - 20) / 2
    body.append(f'<rect class="box" x="20" y="{y2:.1f}" width="{cw:.1f}" height="54" rx="8"/>')
    body.append(f'<text class="box-name" x="32" y="{y2 + 20:.1f}">Recorded history: at most 2 orders per message</text>')
    body.append(f'<text class="box-text" x="32" y="{y2 + 39:.1f}">2 concurrent calls &lt;= limit of 4 -> unbounded gather looks green</text>')

    rx = 20 + cw + 20
    body.append(f'<rect class="box-hot" x="{rx:.1f}" y="{y2:.1f}" width="{cw:.1f}" height="54" rx="8"/>')
    body.append(f'<text class="box-name-hot" x="{rx + 12:.1f}" y="{y2 + 20:.1f}">Hidden grader inputs: up to 6 orders per message</text>')
    body.append(f'<text class="box-text" x="{rx + 12:.1f}" y="{y2 + 39:.1f}">6 concurrent calls -> 429 errors unless capped (e.g. Semaphore(4))</text>')

    height = y2 + 70
    (OUT / "kb-helpdesk-services.svg").write_text(
        doc(height, "helpdesk-services: live services and root-only logs behind F5–F8", body,
            subtitle="Setup tasks O1–O4 reuse this container image with separate worker, PydanticAI, and LangGraph exercises.")
    )


# ================================================================ ZenML Bench charts


def zenml_charts() -> None:
    zb_overview_chart()
    zb_how_a_run_works_chart()

    grid_chart(
        "zb-b3-grading",
        "B3 (nightly): how the grader checks content-aware caching",
        ["run 1", "run 2", "run 3", "run 4", "run 5"],
        [
            Panel(
                "A correct fix: cache key tracks the file's contents (e.g. content hash or file_dependencies)",
                [
                    GridRow("data file", [Cell("plain", "a"), Cell("plain", "a"), Cell("plain", "b"), Cell("plain", "b"), Cell("plain", "c")]),
                    GridRow("load_data", [Cell("ok", "ran"), Cell("cached", "cached"), Cell("ok", "ran"), Cell("cached", "cached"), Cell("ok", "ran")]),
                    GridRow("train (3s)", [Cell("ok", "ran"), Cell("cached", "cached", ring=True), Cell("ok", "ran", ring=True), Cell("cached", "cached", ring=True), Cell("ok", "ran", ring=True)]),
                ],
                "Scores match every fixture; train is cached iff data is unchanged -> reward 1",
            ),
            Panel(
                "The obvious fix: enable_cache=False on load_data",
                [
                    GridRow("load_data", [Cell("ok", "ran"), Cell("ok", "ran"), Cell("ok", "ran"), Cell("ok", "ran"), Cell("ok", "ran")]),
                    GridRow("train (3s)", [Cell("ok", "ran"), Cell("fail", "ran", "new artifact id -> miss"), Cell("ok", "ran"), Cell("fail", "ran", "new artifact id -> miss"), Cell("ok", "ran")]),
                ],
                "Scores are right, but train re-runs every time -> reward 0",
            ),
        ],
        subtitle="Pipeline: load_data(path) -> train(df) -> evaluate(model, df). The grader swaps fixtures a, a, b, b, c at the same path.",
        note="A freshly returned DataFrame gets a new artifact ID and pandas has no content hash, so disabling cache on load_data silently busts train's cache.",
        legend_items=[("ok", "ran"), ("cached", "served from cache"), ("fail", "wrong (should be cached)"), ("ring", "what the grader checks")],
    )

    grid_chart(
        "zb-sampling",
        "B4 (sampling): fresh random sample every run while the loader stays cached",
        ["run 1 (unseen n)", "run 2 (same unseen n)"],
        [
            Panel(
                "Starting state or CachePolicy(expires_after=0) — still cached!",
                [
                    GridRow("load_events (3s)", [Cell("ok", "ran"), Cell("cached", "cached")]),
                    GridRow("sample_events", [Cell("ok", "sample A"), Cell("fail", "cached (sample A)", "expires_after=0 means unset")]),
                    GridRow("review_report", [Cell("ok", "report A"), Cell("fail", "cached (report A)", "identical QA review")]),
                ],
                "Every QA review inspects the exact same 50 events -> reward 0",
            ),
            Panel(
                "Working fix: disable cache on sample_events only",
                [
                    GridRow("load_events (3s)", [Cell("ok", "ran"), Cell("cached", "cached", ring=True)]),
                    GridRow("sample_events", [Cell("ok", "sample A"), Cell("ok", "sample B", "fresh draw", ring=True)]),
                    GridRow("review_report", [Cell("ok", "report A"), Cell("ok", "report B", "matches sample B", ring=True)]),
                ],
                "Loader stays cached, samples differ, each report matches its own sample -> reward 1",
            ),
        ],
        subtitle="Pipeline: load_events() -> sample_events(events, n) -> review_report(sample).",
        legend_items=[("ok", "ran"), ("cached", "served from cache"), ("fail", "wrong (stale cache)"), ("ring", "what the grader checks")],
        left=185.0,
    )

    cols10 = ["08-30", "09-02", "09-03", "09-04", "09-05", "09-06", "09-07", "09-08", "09-09", "typo*"]
    grid_chart(
        "zb-b10-history",
        "B10 & B10H (daily_report): seeded runs in the store before the agent starts",
        cols10,
        [
            Panel(
                "",
                [
                    GridRow(
                        "scheduled",
                        [
                            None,
                            Cell("ok", "ok"),
                            Cell("fail", "failed", "summarise: bad regions (B10H)", ring=True),
                            Cell("ok", "ok"),
                            Cell("fail", "failed", "load: no file"),
                            Cell("fail", "failed", "write: no dir"),
                            Cell("ok", "ok"),
                            Cell("ok", "ok"),
                            Cell("fail", "failed", "parse: 1,234.50", ring=True),
                            None,
                        ],
                    ),
                    GridRow(
                        "manual",
                        [
                            Cell("fail", "failed", "parse: old ISO"),
                            None, None, None, None, None, None, None, None,
                            Cell("fail", "failed", "09-31 typo (latest)"),
                        ],
                    ),
                ],
            )
        ],
        subtitle="Pipeline: load(date) -> parse -> summarise -> write_report. Only ringed runs are code faults.",
        note="*The manual 09-31 typo ran AFTER 09-09, so it is the most recent failed run overall (a decoy). In B10H, the 09-03 and 09-09 CSVs are moved off the box so the agent must inspect ZenML's recorded traceback or load artifact.",
        bands=[ColBand(0, 3, "added in B10H (+4 runs)"), ColBand(4, 9, "present in B10 & B10H (6 runs)")],
        left=120.0,
    )

    cols14 = ["08-24", "08-25", "08-26", "08-27", "08-28", "09-08"]
    grid_chart(
        "zb-b14-history",
        "B14 & B14H (daily_report): finding the busiest completed backfill run",
        cols14,
        [
            Panel(
                "B14: largest completed backfill run (totals from seeded CSVs)",
                [
                    GridRow(
                        "backfill",
                        [
                            Cell("ok", "15,753"),
                            Cell("ok", "16,237"),
                            Cell("fail", "30,165", "largest, but failed"),
                            Cell("ok", "16,506", "B14 answer", ring=True),
                            Cell("fail", "no file"),
                            None,
                        ],
                    ),
                    GridRow(
                        "scheduled",
                        [None, None, None, None, None, Cell("ok", "22,383", "not a backfill")],
                    ),
                ],
            ),
            Panel(
                "B14H: re-processed days — rule: \"the latest completed processing of each day counts\"",
                [
                    GridRow(
                        "first run",
                        [
                            Cell("ok", "12,223"),
                            Cell("ok", "16,179", "still counts (v2 failed)"),
                            Cell("fail", "17,170", "largest summary"),
                            Cell("ok", "16,689", "superseded by v2"),
                            Cell("fail", "no file"),
                            None,
                        ],
                    ),
                    GridRow(
                        "re-run (v2)",
                        [
                            None,
                            Cell("fail", "16,986", "latest, but failed"),
                            Cell("ok", "16,419", "B14H answer (v5)", ring=True),
                            Cell("ok", "14,951", "counts for 08-27"),
                            None,
                            None,
                        ],
                    ),
                    GridRow(
                        "scheduled",
                        [None, None, None, None, None, Cell("ok", "22,383", "not a backfill")],
                    ),
                ],
            ),
        ],
        subtitle="Numbers inside cells are the day's summary totals. Every simpler filtering rule picks a different run.",
        note="Other scheduled runs (09-05 to 09-09) and the manual 09-31 typo also sit in the store; 09-08 is shown because it has the highest scheduled total.",
        gap_after=4,
        left=130.0,
    )

    zb_model_promotion_chart()
    zb_b1_roots_chart()

    flow_chart(
        "zb-research-chain",
        "R1 & R2: the lineage chain the grader walks before scoring a model",
        [
            Lane(
                "",
                [
                    Box("production", "version of research_model"),
                    [
                        Box("linked run", "completed run of research pipeline -> train step (+ row digest) -> model output", "good"),
                        Box("manual link", "artifact attached directly without a completed run -> rejected (reward 0)", "hot"),
                    ],
                    Box("hidden score", "grader's evaluator computes gap_closed on unseen data", "good"),
                ],
            )
        ],
        subtitle="ZenML lets you attach any artifact to any model version, so a link alone is not evidence.",
        note="The train step also logs n_train_rows and a digest of the training rows, so training on the full dataset is caught.",
        legend_items=[("box-good", "verified lineage path"), ("box-hot", "shortcut refused by grader")],
    )


# ================================================================ Kitaru Bench charts


def kitaru_charts() -> None:
    kb_overview_chart()
    kb_how_a_run_works_chart()

    story_chart(
        "kb-storefront",
        "storefront (Larkspur Goods): 60 days of history, 1 June to 30 July 2026",
        d("2026-06-01"),
        d("2026-07-30"),
        [
            Row("agent release", [
                Bar(d("2026-06-01"), d("2026-06-30"), "neutral", "1.3.0"),
                Bar(d("2026-07-01"), d("2026-07-21"), "neutral", "1.4.0"),
                Bar(d("2026-07-22"), d("2026-07-30"), "neutral", "1.4.1"),
            ], tag="C4"),
            Row("euro reply text", [
                Bar(d("2026-07-01"), d("2026-07-30"), "problem", "euro card replies quote 100x (money right; decoy for D6)"),
            ], tag="C2"),
            Row("polite-closing check", [
                Bar(d("2026-06-01"), d("2026-07-30"), "decoy", "wrongly fails idle timeouts (where customer just left)"),
            ], tag="C3/D8"),
            Row("shipping over-refund*", [
                Bar(d("2026-06-15"), d("2026-06-28"), "problem", "15–28 Jun: ~1 in 7 full refunds also pays shipping"),
            ], tag="D6"),
            Row("order service outage*", [
                Bar(d("2026-06-21"), d("2026-06-21"), "problem", "21 Jun 10:00–20:00: 4–6 retries/conv (32)"),
            ], tag="D9"),
            Row("summer-sale traffic*", [
                Bar(d("2026-07-04"), d("2026-07-04"), "problem", "4 Jul: +120 normal-cost conversations"),
            ], tag="D9"),
            Row("served model swap*", [
                Bar(d("2026-07-09"), d("2026-07-12"), "partial", "9 Jul: ~35% -> 13 Jul: 100% (2.2x slower, no release)"),
                Bar(d("2026-07-13"), d("2026-07-18"), "problem"),
            ], tag="C1h/D7"),
        ],
        [d("2026-06-01"), d("2026-06-15"), d("2026-07-01"), d("2026-07-15"), d("2026-07-30")],
        subtitle="Base history (2,997 runs) for C1–C7; diagnosis history (3,117 runs) adds the four * rows for C1h and D6–D9.",
        note="Standing faults (repeated lookups, late/double refunds, curt replies, idle timeouts) occur throughout all 60 days; see table below.",
        legend_overrides={"partial": "partial rollout (~35%)", "problem": "what a task must find"},
    )

    story_chart(
        "kb-clinic",
        "clinic (Fernhill Vets): overlapping changes, 1 June to 20 July 2026",
        d("2026-06-01"),
        d("2026-07-20"),
        [
            Row("agent release", [
                Bar(d("2026-06-01"), d("2026-06-20"), "neutral", "1.1.0"),
                Bar(d("2026-06-21"), d("2026-06-24"), "decoy", "1.2.0 rollout (decoy)"),
                Bar(d("2026-06-25"), d("2026-07-08"), "neutral", ""),
                Bar(d("2026-07-09"), d("2026-07-20"), "partial", "1.3.0: fixes search only"),
            ], tag="D2/D5"),
            Row("git commits (5 total)", [
                Bar(d("2026-06-01"), d("2026-06-01"), "commit", "0"),
                Bar(d("2026-06-20"), d("2026-06-20"), "commit", "1"),
                Bar(d("2026-06-26"), d("2026-06-26"), "commit", "2"),
                Bar(d("2026-07-01"), d("2026-07-01"), "commit", "3", highlight=True),
                Bar(d("2026-07-08"), d("2026-07-08"), "commit", "4"),
            ], tag="D3"),
            Row("wrong-clinic bookings", [
                Bar(d("2026-06-15"), d("2026-07-20"), "problem", "15 Jun: ~7 in 10 booked next door (98 still happen under 1.3.0)"),
            ], tag="D1/D5"),
            Row("double clinic search", [
                Bar(d("2026-06-15"), d("2026-07-08"), "neutral", "visible symptom; stopped by 1.3.0"),
            ]),
            Row("customer complaints", [
                Bar(d("2026-06-17"), d("2026-07-20"), "decoy", "13 later complaint chats (not the bad bookings)"),
            ], tag="D1"),
            Row("partner new patients", [
                Bar(d("2026-06-22"), d("2026-07-20"), "problem", "22 Jun: 3x model calls -> drives cost rise (207)"),
            ], tag="D2"),
            Row("litter group bookings", [
                Bar(d("2026-06-27"), d("2026-07-20"), "problem", "27 Jun: 4–7 pets rightly refused 422 (67; nothing broken)"),
            ], tag="D4"),
            Row("cut-off replies", [
                Bar(d("2026-07-01"), d("2026-07-20"), "problem", "1 Jul: finish_reason=length after commit 3 (288)"),
            ], tag="D3"),
        ],
        [d("2026-06-01"), d("2026-06-15"), d("2026-07-01"), d("2026-07-15")],
        subtitle="3,211 conversations, 3 releases, 5 dated git commits. Multiple changes overlap so naive time-correlation picks the decoy.",
        note="Commits: 0 initial 1.1.0 (29 May, pinned to start edge); 1 release 1.2.0; 2 litter-offer prompt; 3 config max_tokens 400->120 (ringed: D3 cause, no release); 4 release 1.3.0.",
        legend_overrides={"partial": "partial fix (1.3.0)", "ring": "D3 culprit commit"},
    )

    kb_exports_langfuse_chart()
    kb_exports_nightly_chart()

    flow_chart(
        "kb-replay",
        "helpdesk worlds: how Kitaru's tool policy protects real side effects during replay",
        [
            Lane(
                "",
                [
                    Box("recorded run", "every model and tool call captured by Kitaru's adapter"),
                    Box("replay", "re-runs the agent against a new release or model setting"),
                    Box("tool policy", "configured per tool; default is live"),
                    [
                        Box("recorded", "answers from the recording; nothing reaches external services", "good"),
                        Box("live (default!)", "calls the real tool -> issue_refund hits finance service -> customer paid twice", "hot"),
                    ],
                ],
            )
        ],
        subtitle="Every replay task checks the root-only finance ledger before and after. One new refund row scores 0.",
        legend_items=[("box-good", "safe during replay"), ("box-hot", "triggers real payment (reward 0)")],
    )

    kb_helpdesk_services_chart()


if __name__ == "__main__":
    zenml_charts()
    kitaru_charts()
    print("\n".join(sorted(p.name for p in OUT.glob("*.svg"))))
