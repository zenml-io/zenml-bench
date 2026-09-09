# Baseline — task B5 `custom-materializer`

Date: 2026-09-09. Same setup as `level1.md`. 3 attempts per cell. Raw rows: `b5-custom-materializer-baseline.jsonl`. The grader went through two corrections during this baseline (both shared-store cache cases, see `docs/findings.md`); the Claude Code bare cell was re-run after the second.

| harness | model | condition | pass rate | skill read | ZenML materializer written |
|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | – | 3/3 |
| claude-code | claude-opus-5 | + skill | 3/3 | see jsonl | 3/3 |
| codex | gpt-5.6-terra | bare | 3/3 | – | 2/3 (one made the type picklable) |
| codex | gpt-5.6-terra | + skill | 3/3 | 3/3 | 3/3 |

Cheap models (bare): haiku-4.5 3/3, gpt-5.4-mini 3/3, all six by making the type picklable rather than writing a materializer (`used_custom_materializer=0`).

## Findings

1. **Saturated at both tiers.** The symptom-only instruction did not stop anyone: every agent recognised "cannot pickle" + "load by name" as a materializer problem or as a `__getstate__` problem.
2. **Mechanism splits by model tier.** Frontier models reach for ZenML's materializer (11/12); cheap models reach for Python's pickle protocol (6/6). Both are valid by outcome; the metric shows the difference without grading on it. This is the kind of signal a "did the skill help" study can use even when pass rates are flat.
3. **Two more grader lessons** (now in `docs/task-authoring.md`): a cached step's output belongs to an earlier run; and "latest version by name" can be a debug run's version while the graded run is served an older one. Assert on membership (a version of the named artifact), never on identity with "latest".
