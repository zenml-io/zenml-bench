# With vs without ZenML: the R1 comparison under a stated clock

Date: 2026-09-10. Tasks `r1-clock-improve-within-budget` (ZenML) and `r1-bare-clock-improve-within-budget` (no framework): the same problem, data, screening seeds, 12-experiment budget, hidden set and anchors as R1 / R1-bare, plus one rule the pilot lacked: the agent is told it has 25 minutes and 2 CPUs' worth of compute, and Harbor enforces both (`[agent] timeout_sec = 1500`, `[environment] cpus = 2`). Why a clock and not a compute cost: `docs/decisions.md` 2026-09-10. Bare condition (no skill, no MCP), `--env-file .env`, k = 5 per cell, `-n 1` so trials never ran concurrently with each other. Raw rows: `r1-clock-improve-within-budget-cmp.jsonl`, `r1-bare-clock-improve-within-budget-cmp.jsonl` (jobs `cmp-*`). Total spend for the 20 trials: $12.13 (harness figures).

Four checks under Harbor (`scripts/verify_task.py`), both clock tasks and the three tasks they derive from, after the training-slice check was added: oracle 5/5, nop 0, every shortcut 0 (R1 7, R2 9, R1-bare 7; the clock tasks inherit R1's and R1-bare's), every alternative 1 (R1 4, R2 3, R1-bare 3). B10 re-verified after its instruction change: all four pass.

Column meanings: `hidden` = hidden-data log loss of the promoted model as scored by the frozen verifier (lower is better; baseline 0.659, reference 0.458); `gap` = clipped share of that gap closed; `runs/rows` = pipeline runs in the store or rows in `results.tsv` (the budget metric); `≥2/≥3 seeds` = distinct seeds behind the promoted config; `first run` = minutes from the agent's start to its first entrypoint call; `scripts` = Python invocations that are not the entrypoint (off-loop search); `minutes` = agent-phase wall clock; `max_train_rows` was 1050 and `slice_violations` 0 in all 20 trials.

## Per cell

| harness | variant | finished | median hidden | median gap | median runs/rows | ≥2 seeds | ≥3 seeds | median first run (min) | median scripts | median minutes | mean cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| opus-5 | ZenML | 5/5 | 0.426 | 1.0 | 3 | 2/5 | 0/5 | 4.1 | 10 | 12.8 | $0.91 |
| opus-5 | bare | 5/5 | 0.433 | 1.0 | 6 | 4/5 | 3/5 | 1.6 | 6 | 7.8 | $0.62 |
| terra | ZenML | 5/5 | 0.272 | 1.0 | 5 | 3/5 | 0/5 | 1.6 | 20 | 9.0 | $0.68 |
| terra | bare | 5/5 | 0.406 | 1.0 | 12 | 3/5 | 2/5 | 0.4 | 2 | 1.6 | $0.21 |

## Per trial

| harness | variant | trial | reward | hidden | seeds | runs | first run (min) | entry | scripts | minutes | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| opus-5 | ZenML | DNUTb2W | 1 | 0.431 | 1 | 3 | 3.5 | 4 | 10 | 15.1 | $1.02 |
| opus-5 | ZenML | VfGkiVK | 1 | 0.363 | 2 | 3 | 4.1 | 3 | 14 | 9.4 | $1.14 |
| opus-5 | ZenML | VsenBWa | 1 | 0.426 | 1 | 2 | 11.7 | 2 | 7 | 13.2 | $0.77 |
| opus-5 | ZenML | Xps88gT | 1 | 0.434 | 2 | 3 | 10.3 | 3 | 10 | 12.8 | $0.92 |
| opus-5 | ZenML | varcmSM | 1 | 0.424 | 1 | 1 | 3.0 | 1 | 8 | 7.8 | $0.71 |
| opus-5 | bare | EGUT5oq | 1 | 0.439 | 5 | 6 | 1.9 | 3 | 9 | 7.8 | $0.74 |
| opus-5 | bare | Wnv2keW | 1 | 0.434 | 3 | 4 | 6.6 | 2 | 6 | 8.7 | $0.61 |
| opus-5 | bare | dYBx83F | 1 | 0.42 | 1 | 2 | 1.6 | 2 | 12 | 7.2 | $0.75 |
| opus-5 | bare | fe45v4y | 1 | 0.43 | 3 | 12 | 0.8 | 7 | 0 | 10.5 | $0.55 |
| opus-5 | bare | mpUMKDv | 1 | 0.433 | 2 | 11 | 0.4 | 5 | 2 | 2.2 | $0.46 |
| terra | ZenML | HdaonnJ | 1 | 0.346 | 2 | 4 | 1.6 | 4 | 19 | 6.6 | $0.62 |
| terra | ZenML | HeEQhZF | 1 | 0.229 | 1 | 7 | 1.9 | 7 | 24 | 9.0 | $0.80 |
| terra | ZenML | KdHyhjS | 1 | 0.221 | 2 | 7 | 2.5 | 7 | 34 | 13.9 | $0.88 |
| terra | ZenML | TPi5Da9 | 1 | 0.272 | 1 | 5 | 1.2 | 5 | 20 | 10.4 | $0.63 |
| terra | ZenML | sJmW8sv | 1 | 0.361 | 2 | 3 | 1.3 | 4 | 14 | 5.5 | $0.48 |
| terra | bare | 9pF6mWz | 1 | 0.461 | 3 | 12 | 0.5 | 4 | 2 | 1.6 | $0.17 |
| terra | bare | Aq8ZLnD | 1 | 0.376 | 3 | 12 | 0.7 | 3 | 2 | 1.7 | $0.18 |
| terra | bare | PigrpN9 | 1 | 0.429 | 1 | 12 | 0.4 | 11 | 10 | 3.0 | $0.35 |
| terra | bare | iNga5mz | 1 | 0.396 | 1 | 12 | 0.2 | 6 | 2 | 1.4 | $0.18 |
| terra | bare | y4R6YHe | 1 | 0.406 | 2 | 12 | 0.3 | 8 | 0 | 1.6 | $0.17 |

## Reading it

1. **Finished rate no longer separates the variants: 20/20.** The pilot's headline (opus finished ZenML 3/3 but bare 1/6) was the unstated 40-minute timeout, not the missing framework. Told the clock exists, opus promoted a "safety net" model at minute 1–4 in both variants (every one of its 10 trials re-promoted at least once; its own words: "Promoting immediately as a safety net", "Insurance promotion now") and finished in 2–15 minutes. So the earlier finding "the ZenML framing makes opus converge" is withdrawn; a stated budget does that.
2. **The hidden metric did separate the variants for Codex, and in ZenML's favour.** Codex with ZenML: 0.221–0.361 (median 0.272); Codex bare: 0.376–0.461 (median 0.406). The two sets do not overlap (rank-sum, two-sided, p ≈ 0.008), but five trials per cell and one model are a lead, not a result. Opus showed no difference (0.426 vs 0.433 medians; 0.36–0.43 vs 0.42–0.44).
3. **What Codex did differently is visible in the counts, not just the metric.** Without ZenML it treated the 12 rows *as* the search: 12/12 rows in every trial, 0–10 off-loop scripts (median 2), first row at 0.2–0.7 min, done in 1.4–3.0 min, then it stopped because the budget was spent. With ZenML it did the search off-loop (14–34 scripts), spent 3–7 runs recording candidates, promoted after each improvement (2–6 promotions per trial), and kept going until quality plateaued (5.5–13.9 min). The extra minutes went into search, and the search found the feature-selection / kernel / class-conditional-mixture structure that the fast bare trials never reached. Per-run cost does not explain this: an official run costs about 3.5 s with ZenML and 1 s without (measured on the host), both negligible against a 25-minute clock. The difference is in what the agent takes a run to *be*: with ZenML a run is a recorded experiment that a version collects evidence under, so runs are spent deliberately; in the bare loop a run is the cheapest way to try a config, so the budget is spent as fast as it can be typed.
4. **Opus moved the other way on evidence, and on where it searched.** Opus bare confirmed on ≥3 seeds in 3/5 trials and ran 4–12 rows; opus ZenML confirmed on ≥3 seeds in 0/5 and ran 1–3 pipeline runs with 7–14 off-loop scripts. Same model, same rule text: with a pipeline in front of it, opus screened outside the loop and used the loop only to record the winner (as in the pilot), while with a bare script it screened *in* the loop, which produced seed coverage as a side effect. Neither variant produced R2-style evidence by design; R1's rule allows single-seed promotion and both harnesses used that freedom.
5. **Quality fell for opus relative to the pilot (0.43 vs 0.24 median hidden) and cost fell with it ($0.6–0.9 vs $2–3.4 per trial).** The 25-minute clock cut the search that found the generator's structure in the 40-minute pilot; opus stopped after 8–15 minutes in every trial, well short of the limit, once its screening "plateaued". Codex with ZenML used its time better (up to 14 min) and got the pilot-grade numbers (0.22) at a third of the pilot's opus cost.
6. **Nobody opened the docs in 20/20 trials** (`docs_read` False throughout); the README's client snippets carried every promotion and evidence check, as in the pilot.

## Confounds that remain

- **Host load.** 78 load samples were taken every two minutes during the run; the first 40 minutes (the first four opus ZenML trials) overlapped with other agents' Harbor trials on the same machine (load 12–16 on 18 cores, up to 9 containers); after 07:45 the host held only this run (load 4–9). The 2-CPU quota bounds a trial from above, not from below, so those four trials may have been slightly slower; they finished in 8–15 min with 10–17 min to spare, so the clock did not bind on them. The codex ZenML cell and both bare cells ran on a quiet host.
- **Run order.** Cells ran in a fixed order (opus ZenML, codex ZenML, opus bare, codex bare), not interleaved; nothing in the trajectories depends on the time of day, but the load confound above is correlated with it.
- **Model latency is the clock's real cost.** Opus finished 10–20 minutes early in every trial, so the 25-minute limit did not cut off any search directly; it changed behaviour by being *stated*. A tighter limit (15 min) would test whether the early promotion survives real pressure.
- **One dataset, two models, five trials per cell.** The Codex separation is clean but small-sample; the opus null could hide an effect of the size seen for Codex. Doubling k on the Codex cells is the cheapest next step ($3 per five trials).
- **The 12-run rule stayed.** In the bare variant it binds as a row count that Codex exhausted in two minutes; whether Codex would keep searching without it (or with a 25-row budget) is untested.

## What to run next

- Codex k = 10 on both variants to firm up the hidden-metric gap; if it holds, the same pair with the R2 evidence rule (three seeds) to see whether ZenML's per-version run collection makes the confirmation cheaper for the agent than a TSV.
- A 15-minute clock, to see whether early promotion holds when the clock actually binds.
- Difficulty tags set from this run: both clock tasks `easy` (20/20 pass); the hidden metric is the signal, as for R1.
