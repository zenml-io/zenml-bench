# Baseline — task B2 `script-to-pipeline`

Date: 2026-09-10. Frontier tier only, bare condition, 3 attempts per cell (Harbor 0.22.0, sealed network with the model API allowlisted, `-n 2`). Raw rows: `b2-script-to-pipeline-baseline-l2.jsonl`. The grader reruns the agent's `train.py` on the visible data and on a hidden file and compares the recorded `accuracy` artifact with what the original script prints.

| harness | model | condition | pass rate | steps | hit "Unable to unpack step artifact" | read docs | pipeline runs | median tokens | mean cost | mean minutes |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | 4 (load, prepare, train, evaluate) 3/3 | 0/3 | 3/3 | 5–7 | 452k | $0.54 | 2.5 |
| codex | gpt-5.6-terra | bare | 3/3 | 4 3/3 | 3/3 | 3/3 | 6–7 | 412k | $0.25 | 1.8 |

## What they did

All six produced the same shape: a loading step, a preparation step returning the four splits as a `Tuple[Annotated[...], ...]`, a training step whose output is named `model`, and an evaluation step returning `Annotated[float, "accuracy"]`, then ran the pipeline several times (including with a copied or modified CSV) and read the artifacts back to compare with the original script's printed number. One Claude Code trial used `ArtifactConfig(name="model")`; the rest used plain `Annotated[..., "model"]`, which the grader accepts (it looks for an output artifact named `model`).

**All three Codex trials hit the B9 trap**: their first `prepare` step returned `train_test_split(...)` directly under a four-way `Tuple` annotation and failed at run time with `StepInterfaceError: Unable to unpack step artifact` (ZenML treats a non-literal tuple return as one output). Each recovered on the next edit by unpacking into four names and returning them explicitly. Claude Code wrote the literal tuple return from the start in 3/3.

## Findings

1. **Saturated (6/6)**; the task is a conversion exercise that both harnesses do routinely. Worth keeping as the entry-level task of the "build" family (it exercises `@step`/`@pipeline`, typed outputs, named artifacts and the CLI entrypoint) and as a regression test for the tuple-return trap.
2. **The tuple-return trap fires reliably for Codex (3/3) and never for Claude Code (0/3)**, the same asymmetry as in B9's first baseline. The error message is clear enough that recovery is one step, so it costs tokens rather than correctness. Docs item stands (from B9): the step-outputs page should say that a `Tuple` return must be a literal tuple expression.
