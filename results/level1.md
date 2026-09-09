# Level 1 baseline — task B3 `stale-cache`

Date: 2026-09-09. ZenML 0.96.4, Harbor 0.22.0, OrbStack, network sealed except the model API during the agent's turn. Skill condition = `zenml-io/skills@e8534cad` (`pipeline-authoring`, `quick-wins`). 3 attempts per cell. Raw rows: `b3-stale-cache-baseline.jsonl`.

| harness | model | condition | pass rate | skill read | docs read | median tokens | mean cost |
|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | – | 3/3 | 472k | $0.62 |
| claude-code | claude-opus-5 | + skill | 3/3 | **0/3** | 3/3 | 896k | $0.82 |
| codex | gpt-5.6-terra | bare | 3/3 | – | 3/3 | 288k | $0.20 |
| codex | gpt-5.6-terra | + skill | 3/3 | 3/3 | 3/3 | 466k | $0.28 |

Fix chosen (from the patches in the trajectories): Codex bare used the hash-as-step-input approach every time; Codex with the skill used `CachePolicy(cache_func=…)` or `file_dependencies` in 2/3, i.e. the skill moved it toward the built-in feature. Claude Code used `CachePolicy(file_dependencies=…)` in 4/6 regardless of condition.

## Findings

1. **The task is too easy for frontier models today.** 12/12. It stays in the suite as the entry point and as a regression task, but the benchmark needs harder tasks to separate harnesses. Difficulty estimate updated to "easy, saturated".
2. **Claude Code never read the skill, 0/3.** Harbor copied both skills into `$CLAUDE_CONFIG_DIR/skills`; no `Skill` tool call and no read of any `SKILL.md` in any trajectory. Codex read `pipeline-authoring/SKILL.md` in full, plus `references/external-data.md`, in 3/3. Same finding as Supabase (skill activation is harness-dependent and often low). Action: check whether Claude Code lists these skills at all in its context (their `description:` frontmatter may not match a caching task), and test a rewritten description.
3. **Everyone read the offline docs, 12/12**, usually via `rg` on `llms-full.txt` for "cache". The 0.96 docs on cache policies are good enough that the skill adds little for this task.
4. **The skill costs tokens without changing the outcome here.** Claude Code's median went from 472k to 896k tokens with the skill present but unread; the extra is likely the skill listing plus more exploration, not the skill body. Worth checking before concluding anything.
5. **Grader bug found by the first real trial** (fixed): the store is shared, so an agent that runs the pipeline before grading warms the cache; graders must only assert "executed" on unseen inputs. Details in `docs/findings.md`.
