# Cheaper models

Same setup as `level1.md`; bare condition only; 3 attempts per cell. Raw rows: `<task>-baseline-cheap.jsonl`.

## B3 `stale-cache` (2026-09-09)

| harness | model | pass rate | failure modes |
|---|---|---|---|
| claude-code | claude-haiku-4-5 | **1/3** | one trial disabled caching on `train` (fails "unchanged rerun stays cached"); one trial never fixed the staleness (all five scores equal) |
| codex | gpt-5.4-mini | 3/3 | – |

First non-saturated cell in the benchmark. B3 separates models at this tier even though opus-5 and gpt-5.6-terra both hit 100%.
