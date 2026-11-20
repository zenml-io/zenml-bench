# Kitaru Level 1: first baseline on `kitaru-c2-finding-to-check`

Run on 2026-11-20 on Modal (workspace `zenml-io`, environment `dev`), Harbor 0.26.0, Kitaru 0.27.7, bare condition (CLI, SDK, offline docs; no skills, no MCP), 5 attempts per cell. Rows: `results/kitaru-c2-finding-to-check-baseline.jsonl`. Raw jobs: `jobs/kbaseline-c2-*` (not committed).

The task: register an evaluator that fails conversations whose reply states 100 times the refunded amount. The grader runs the registered evaluator on 120 hidden conversations (40 affected) and needs precision and recall of at least 0.9.

| harness + model | passed | median cost | read recorded sessions | ran its evaluator before stopping |
|---|---|---|---|---|
| Claude Code + `claude-sonnet-5-5` | 5 / 5 | US$0.23 | 5 of 5 trials | 5 of 5 |
| Codex + `gpt-5.6-terra` | 4 / 5 | US$0.33 | 5 of 5 | 5 of 5 |
| Codex + `gpt-5.4-mini` | 0 / 5 | US$0.05 | 3 of 5 | 3 of 5 |

Total spend about US$3.40. Agent time: 25–50 s for `gpt-5.4-mini`, about 2 min for `gpt-5.6-terra`, 2–13 min for `claude-sonnet-5-5`.

## What the six failures were

Read from each failed trial's `verifier/metrics.json` and the evaluator source in its trajectory.

- **`gpt-5.4-mini`, four trials: an evaluator that fails nothing** (precision 0, recall 0, a verdict on every session). The sources guess at the data: `node.payload` or text-matching `str(node.inputs)` for a currency sign that the tool arguments do not contain, or an amount pattern that cannot read `€3,636.00` (thousands comma). Two of the four never opened a recorded session; none compared its evaluator's verdicts with a session it knew to be affected.
- **`gpt-5.4-mini`, one trial, and `gpt-5.6-terra`, one trial: caught every affected session, plus false alarms on one planted near-miss** (precision 0.74 and 0.82). Every false alarm is a correct partial refund in euros whose order total is exactly 100 times the refund ("I've refunded €10.55 of your €1,055.00 order"). The evaluator asks "does any amount in the reply equal 100 times the refund?" and not "is the refund's own amount stated?".
- The earlier single smoke trial of `gpt-5.4-mini` (not in the table) used `node.input` / `node.output`; the real attributes are `inputs` / `outputs`. Its evaluator crashed on all 106 hidden sessions that have a refund.

## Reading

- The task separates a small model from two large ones and is close to saturated for the large ones (9 of 10). By the proposal's rule it needs a harder variant before it carries weight on a leaderboard; as a regression check for Kitaru's agent-facing aids it is useful now, because the small model's failures are all "did not look" or "did not test".
- With 5 attempts per cell, 4/5 against 5/5 is not a difference.
- Not done: the `+ skills` and `+ MCP` conditions; a read of every passing trajectory.
