# Baseline — task B6 `model-promotion`

Date: 2026-09-10. Frontier tier only, bare condition, 3 attempts per cell (Harbor 0.22.0, sealed network with the model API allowlisted, `-n 2`). Raw rows: `b6-model-promotion-baseline-l2.jsonl`. Seeded store: version 1 (linear, `val_mae` 4.857) and version 2 (forest, 5.971) of `demand_forecaster`, plus one inference run on `version="latest"`. The grader promotes the worst version itself after the first hidden-batch run and reruns on the same batch.

| harness | model | condition | pass rate | promoted via | inference change | saw a cached `predict` while testing | read docs | median tokens | mean cost | mean minutes |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | `set_stage` / client 3/3 | `ModelStages.PRODUCTION` + `enable_cache=False` 3/3 (one also passed the model artifact as a step input) | 3/3 | 3/3 | 461k | $0.53 | 2.4 |
| codex | gpt-5.6-terra | bare | 3/3 | CLI `model version update --stage` 2/3, client 1/3 | `ModelStages.PRODUCTION` + `enable_cache=False` 3/3 | 1/3 | 3/3 | 303k | $0.15 | 0.9 |

`predict_cached_after_repromotion` (grader metric) was 0 for all six: nobody's inference served a stale model after the grader's re-promotion.

## What they did

Every trial listed the versions with the client, read `run_metadata["val_mae"]`, promoted version 1 (Codex mostly through `zenml model version update demand_forecaster 1 --stage production`, Claude Code through `Client().get_model_version(...).set_stage("production")`), and changed the pipeline's `Model(version=...)` to `ModelStages.PRODUCTION` (six of six used the enum rather than the string). All six then disabled caching on `predict`, citing the instruction's "even if that run uses the same input batch" clause; four of them also *observed* the trap first: their post-promotion test run showed `predict` as `cached` with the old predictions, and the fix followed. Codex was fast (under a minute each) and did not read ZenML source; Claude Code ran more verification (promote, run, flip, run, flip back) and one trial additionally passed the production model artifact into `predict` as a step input.

## Findings

1. **Saturated (6/6)**, because the instruction names the failure mode ("same input batch"). Without that clause the grader would have caught the `stage_without_cache_fix` behaviour that four trials produced *before* they fixed it; a harder variant simply drops the clause and asks only that "inference follows production", which would measure whether an agent tests a promotion flip on its own.
2. **The cache-across-promotion trap is real and visible**: ZenML does not put the model version in the step cache key, so a `predict` step that loads the model from the step context is served from cache after a re-promotion when the batch is unchanged, and the run is *linked* to the new version while carrying the old predictions. Docs item: the model-control-plane page should say this next to the "load the production model in a step" example, and recommend passing the model artifact as a step input (it then becomes part of the cache key) or a `CachePolicy`.
3. **Nobody chose the cleanest design** (model artifact as a step input, which records the lineage on the step and keeps caching correct) except one Claude Code trial that did both; `enable_cache=False` is the reflex. A future skill could recommend the input-artifact pattern explicitly.
