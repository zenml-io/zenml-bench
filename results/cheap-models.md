# Cheaper models

Same setup as `level1.md`; bare condition only; 3 attempts per cell. Raw rows: `<task>-baseline-cheap.jsonl`.

## B3 `stale-cache` (2026-09-09)

| harness | model | pass rate | failure modes |
|---|---|---|---|
| claude-code | claude-haiku-4-5 | **1/3** | one trial disabled caching on `train` (fails "unchanged rerun stays cached"); one trial never fixed the staleness (all five scores equal) |
| codex | gpt-5.4-mini | 3/3 | – |

First non-saturated cell in the benchmark. B3 separates models at this tier even though opus-5 and gpt-5.6-terra both hit 100%.

## B5 `custom-materializer`, B7 `kubernetes-settings` (2026-09-09)

| task | haiku-4-5 | gpt-5.4-mini | note |
|---|---|---|---|
| B5 | 3/3 | 3/3 | every cheap trial made the type picklable (ZenML's cloudpickle fallback, `used_custom_materializer=0`); every frontier trial wrote a ZenML materializer |
| B7 | **0/3** | 2/3 | haiku: two trials set no node selector; one wrote `node_selector` (Kubernetes spelling) plus the dead `pod_settings.service_account_name`, and the compile rejected it |

B9 cheap-model cell is being re-run: the first run's zeros were all the "no stray pipelines" collateral check, under an instruction that did not yet state it.
