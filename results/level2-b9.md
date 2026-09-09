# Baseline — task B9 `modernise-old-api`

Date: 2026-09-09. Same setup as `level1.md` (ZenML 0.96.4, Harbor 0.22.0, sealed network, skills `zenml-io/skills@e8534cad`). 3 attempts per cell. Raw rows: `b9-modernise-old-api-baseline.jsonl`.

| harness | model | condition | pass rate | skill read | docs read | median tokens | mean cost |
|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | – | 3/3 | 320k | $0.44 |
| claude-code | claude-opus-5 | + skill | 3/3 | **2/3** | 3/3 | 437k | $0.58 |
| codex | gpt-5.6-terra | bare | 3/3 | – | 3/3 | 561k | $0.28 |
| codex | gpt-5.6-terra | + skill | 3/3 | 3/3 | 3/3 | 775k | $0.34 |

## Findings

1. **Saturated, as expected.** The offline docs carry the 0.39→0.41 migration guide. Stays as the regression task for "unlearn the old API".
2. **Skill activation tracks the description.** Claude Code opened `pipeline-authoring` in 2/3 trials here (its description names `@step/@pipeline decorators`), against 0/3 on the caching task whose subject the description does not mention. Codex opens it whenever present. Same lever Supabase found.
3. **The skill costs tokens, changes nothing here.** +37% median tokens for Claude Code, +38% for Codex, same outcomes.
4. Nobody tripped on the tuple-return trap for long; all trials resolved `StepInterfaceError` on the first rerun.
