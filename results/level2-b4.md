# Baseline — task B4 `nondeterministic-step`

Date: 2026-09-10. Frontier tier only, bare condition, 3 attempts per cell (Harbor 0.22.0, sealed network with the model API allowlisted, `-n 2`). Raw rows: `b4-nondeterministic-step-baseline-l2.jsonl`. The instruction describes the symptom (reviewers get the same rows every day) and the contract (fresh sample every run, loader stays cached, report matches its run).

| harness | model | condition | pass rate | fix used | read docs | pipeline runs | median tokens | mean cost | mean minutes |
|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | `enable_cache=False` on `sample_events` 3/3 | 3/3 | 3–5 | 344k | $0.38 | 1.8 |
| codex | gpt-5.6-terra | bare | 3/3 | `enable_cache=False` on `sample_events` 3/3 (one also on `review_report`) | 3/3 | 2–4 | 283k | $0.18 | 1.2 |

## What they did

All six diagnosed the cause correctly and said so in their final message: nothing is wrong with `df.sample`, the step never runs because its code, inputs and parameters are identical each day. All six grepped the docs snapshot for caching, chose `@step(enable_cache=False)` on the sampler, ran the pipeline two or three times with a small `n`, and read the step statuses back (`cached` loader, `completed` sampler, different samples) before finishing. Nobody used `CachePolicy`, a random parameter, or `expires_after`; nobody disabled caching on the loader. One Codex trial also disabled caching on `review_report` "so it summarises this run's sample", which is redundant (a new DataFrame artifact reruns it anyway) but harmless and passes.

## Findings

1. **Saturated (6/6), and cheap**: the shortest Level 2 task so far (about 1.5 minutes and $0.18–0.40 per trial). It is a good regression test for the caching category alongside B3, not a benchmark item. The shortcut list is what gives it value for training: `expires_after=0` (a validating no-op), seeding the sampler, and blanket cache disabling all score 0.
2. **Nobody reached for `CachePolicy`** even though it is the feature ZenML added for exactly this; `enable_cache=False` is the first thing the docs show. Fine for this task; a harder variant should make `enable_cache=False` insufficient, e.g. the sampler must stay cached *within* a day (same `date` parameter) but not across days, which needs `CachePolicy(cache_func=…)` or a date parameter, and grading both directions.
