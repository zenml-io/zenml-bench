# Baseline — research loops R1, R2 and R1-bare

Dates: 2026-09-09/10. Bare condition (no skill, no MCP), `--env-file .env`, agent timeout 40 min. Raw rows: `r1-improve-within-budget-baseline.jsonl`, `r1-improve-within-budget-baseline-cheap.jsonl`, `r2-screen-then-confirm-baseline.jsonl`, `r1-bare-improve-within-budget-baseline.jsonl`. Metrics come from each trial's `reward.json` as written by the frozen verifier: `gap_closed` (clipped share of the baseline→reference gap closed on hidden data; anchors 0.6585 → 0.4581), `hidden` (hidden-data log loss of the promoted model; lower is better), `seeds` (`n_seeds_backing_promotion`), `runs` (`experiments`: pipeline runs or `results.tsv` rows). "entry" = invocations of the project entrypoint seen in the trajectory; "scripts" = off-pipeline Python scripts/one-liners (search done outside the loop). Costs are the harness's own figures.

## Four checks (Harbor, `scripts/verify_task.py`)

| task | oracle ×5 | nop | shortcuts (all 0) | alternatives (all 1) |
|---|---|---|---|---|
| `r1-improve-within-budget` | 1,1,1,1,1 | 0 | 5/5 | 3/3 |
| `r2-screen-then-confirm` | 1,1,1,1,1 | 0 | 7/7 | 3/3 |
| `r1-bare-improve-within-budget` | 1,1,1,1,1 | 0 | 5/5 | 2/2 |

Monotonicity (R1, one store, four fake promotions): baseline → `gap_closed` 0.000, logistic C=1 → 0.086, random forest → 0.798, reference → 1.000. Reward flips at 0.5.

## Pass rates

| task | harness | model | pass | median hidden | note |
|---|---|---|---|---|---|
| R1 | claude-code | claude-opus-5 | 3/3 | 0.244 | all three found the generator's structure |
| R1 | codex | gpt-5.6-terra | 3/3 | 0.387 | one single-seed promotion |
| R1 | claude-code | claude-haiku-4-5 | 3/3 | 0.477 | in-loop search, 10–11 runs each |
| R1 | codex | gpt-5.4-mini | 3/3 | 0.460 | two single-seed promotions |
| R2 | claude-code | claude-opus-5 | 1/3 concurrent, 2/2 sequential | 0.419 | concurrent failures were timeouts |
| R2 | codex | gpt-5.6-terra | 3/3 | 0.426 | all confirmed on 3–4 seeds |
| R1-bare | claude-code | claude-opus-5 | 0/3 concurrent, 1/3 sequential | 0.333 (the one finish) | every failure a 40-minute timeout with nothing promoted |
| R1-bare | codex | gpt-5.6-terra | 3/3 | 0.450 | used all 12 rows every time |

## Per trial

### R1 `improve-within-budget`

| harness | model | trial | reward | gap | hidden | seeds | runs | entry | scripts | cost |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | opus-5 | VBMxz2a | 1 | 1.00 | 0.251 | 4 | 6 | 3 | 10 | $2.47 |
| claude-code | opus-5 | cxaCEDU | 1 | 1.00 | 0.244 | 5 | 7 | 4 | 34 | $2.04 |
| claude-code | opus-5 | nfLaRqd | 1 | 1.00 | 0.158 | 3 | 4 | 3 | 47 | $3.36 |
| codex | terra | PmK2rND | 1 | 1.00 | 0.430 | 5 | 12 | 12 | 17 | $0.31 |
| codex | terra | dZLjTYy | 1 | 1.00 | 0.387 | 5 | 5 | 2 | 11 | $0.48 |
| codex | terra | mJ6NzKM | 1 | 1.00 | 0.352 | 1 | 1 | 1 | 6 | $0.41 |
| claude-code | haiku-4.5 | MCeBgi9 | 1 | 0.71 | 0.516 | 5 | 11 | 11 | 7 | $0.14 |
| claude-code | haiku-4.5 | cFPcq8k | 1 | 1.00 | 0.456 | 4 | 11 | 11 | 5 | $0.14 |
| claude-code | haiku-4.5 | tixTgQP | 1 | 0.90 | 0.477 | 4 | 10 | 10 | 0 | $0.13 |
| codex | gpt-5.4-mini | 6kSpKdd | 1 | 0.99 | 0.460 | 5 | 5 | 2 | 8 | $0.30 |
| codex | gpt-5.4-mini | 88EBrvr | 1 | 0.99 | 0.460 | 1 | 1 | 1 | 23 | $0.22 |
| codex | gpt-5.4-mini | XAZxr3M | 1 | 1.00 | 0.439 | 1 | 1 | 1 | 24 | $0.24 |

### R2 `screen-then-confirm`

| harness | model | trial | reward | gap | hidden | seeds | runs | entry | scripts | cost |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | opus-5 (3 concurrent) | RyjJEht | 1 | 1.00 | 0.423 | 3 | 3 | 3 | 26 | $1.48 |
| claude-code | opus-5 (3 concurrent) | uPQ65o6 | 0 | 0.00 | – | 0 | 0 | 0 | 4 | $1.02 |
| claude-code | opus-5 (3 concurrent) | xeB3BZ7 | 0 | 0.00 | – | 0 | 0 | 0 | 4 | $1.57 |
| claude-code | opus-5 (sequential) | ovbvp2q | 1 | 1.00 | 0.419 | 5 | 5 | 2 | 19 | $1.01 |
| claude-code | opus-5 (sequential) | zSi2d72 | 1 | 1.00 | 0.241 | 4 | 4 | 2 | 25 | $1.30 |
| codex | terra | EfRgrCj | 1 | 1.00 | 0.426 | 3 | 3 | 3 | 21 | $0.38 |
| codex | terra | Gsap3F6 | 1 | 1.00 | 0.335 | 4 | 4 | 4 | 6 | $0.53 |
| codex | terra | aDFehLz | 1 | 1.00 | 0.453 | 3 | 8 | 8 | 14 | $0.31 |

### R1-bare `improve-within-budget` (no framework)

| harness | model | trial | reward | gap | hidden | seeds | rows | entry | scripts | cost |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | opus-5 (3 concurrent) | iKiDwA8 | 0 | 0.00 | – | 0 | 0 | 1 | 24 | $1.43 |
| claude-code | opus-5 (3 concurrent) | kPr7A9W | 0 | 0.00 | – | 0 | 0 | 0 | 8 | $1.53 |
| claude-code | opus-5 (3 concurrent) | vhrgb3o | 0 | 0.00 | – | 0 | 0 | 0 | 5 | $1.22 |
| claude-code | opus-5 (sequential) | t8vawko | 0 | 0.00 | – | 0 | 0 | 0 | 10 | $0.76 |
| claude-code | opus-5 (sequential) | MFtgVMN | 0 | 0.00 | – | 0 | 0 | 0 | 35 | $1.48 |
| claude-code | opus-5 (sequential) | uj6e8Zm | 1 | 1.00 | 0.333 | 5 | 11 | 3 | 26 | $1.95 |
| codex | terra | 2DtWBA3 | 1 | 1.00 | 0.421 | 3 | 12 | 12 | 5 | $0.28 |
| codex | terra | rjScs4c | 1 | 1.00 | 0.452 | 5 | 12 | 21 | 4 | $0.24 |
| codex | terra | vxfeLXH | 1 | 1.00 | 0.450 | 5 | 12 | 4 | 3 | $0.35 |

## With vs without ZenML (same problem, data, budget, seeds; frontier tier)

| harness | variant | finished | median hidden | median runs/rows | evidence-backed promotion (≥3 seeds) |
|---|---|---|---|---|---|
| claude-code opus-5 | ZenML (R1) | 3/3 | 0.244 | 6 | 3/3 |
| claude-code opus-5 | bare | 1/6 (1/3 sequential) | 0.333 (n=1) | 11 (n=1) | 1/1 |
| codex terra | ZenML (R1) | 3/3 | 0.387 | 5 | 2/3 |
| codex terra | bare | 3/3 | 0.450 | 12 | 3/3 |

Read this table as a pilot, not a result: three trials per cell, and the budget does not bind on compute (see findings). The one difference that survived the re-run is that opus never finished the bare task (1/6 overall, 1/3 sequential), while it finished the ZenML variant 3/3 in 25–35 minutes; in every bare trajectory it was still sweeping when the clock ran out and had not written `best_model.pkl`. Whether the pipeline's explicit "one run = one recorded experiment" framing is what makes opus converge is the question to test next, with k≥5 and a compute-binding budget.

## Findings

1. **Pass/fail is saturated at the frontier; the hidden metric is the signal.** Every finished frontier trial clipped `gap_closed` at 1.0 because every one beat our reference (a regularised gradient-boosting model, hidden 0.458). Opus reached 0.16–0.25 by recognising the data as `make_classification` output (8 noise columns, a rank-8 informative subspace, Gaussian blobs per class) and fitting per-class Gaussian mixtures; Codex reached 0.33–0.45 with feature selection, PCA whitening and RBF-SVM/boosting ensembles. Cheap models (haiku 0.46–0.52, gpt-5.4-mini 0.46) stayed near the reference and are the only trials where `gap_closed` is informative (0.71–0.99).
2. **The 12-run budget did not limit search.** Every trial screened in plain scripts that call `prepare.subsample` and `prepare.evaluate` directly (3–47 such scripts per trial), then spent pipeline runs to record the winner. Haiku is the exception: it searched inside the loop and used 10–11 runs.
3. **Evidence rules work when stated.** R1 allowed single-seed promotion and two trials did it (one terra trial, two gpt-5.4-mini trials); R2 required three seeds and every finished trial complied, reading per-run `val_log_loss` back from the store to compute the mean.
4. **Concurrency on one machine is a confound for opus.** Six opus agents at once → 5/6 timeouts (their own sweeps ran with all cores and fought each other). Sequential re-runs of R2 passed 2/2. Sequential re-runs of R1-bare still timed out 2/3: the behaviour underneath is "search until satisfied, record at the end". One timed-out trial's last message, at minute 38, was "Converged at ~0.194. Let me settle the final ensemble size offline, then commit to official runs"; the one that finished spent its first official run at minute 29. Nothing in the bare loop nudges the agent to record early; in the ZenML variant the same model finished 3/3.
5. **Nobody opened `/opt/zenml-docs`.** The project README carried enough ZenML for every trial; two opus trials also handled the custom-class pickling trap (`cloudpickle.register_pickle_by_value`) unprompted.

Loophole check (training on the full set instead of `prepare.subsample`): inconclusive from the trajectories alone. Agents edit `research.py` with partial edits, so an automatic scan of the last write finds the `subsample` line in 8 trials and nothing decisive in the rest. Final messages of 6 frontier trials state explicitly that `train` still draws from `prepare.subsample`; none claims otherwise; and no finished trial's hidden loss is below what the full-set reference reaches (0.371) except opus's mixture models, whose own screening numbers (val 0.26–0.18 on 1050-row slices) match their hidden scores, which full-set training would not. Task fix: record the training-row count as an *output artifact* of `train` (the grader can then read it from the store) rather than trusting the instruction.
