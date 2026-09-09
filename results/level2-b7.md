# Baseline — task B7 `kubernetes-settings` (corrected grader)

Date: 2026-09-09. Same setup as `level1.md`. 3 attempts per cell. Raw rows: `b7-kubernetes-settings-baseline.jsonl`. The first run of this matrix scored 0/9 on bare and codex-skill because the grader (and reference) used a dead field; see `docs/decisions.md` and `docs/findings.md`. This table is the re-run with the corrected grader.

| harness | model | condition | pass rate | skill read | docs read | read ZenML source | median tokens | mean cost |
|---|---|---|---|---|---|---|---|---|
| claude-code | claude-opus-5 | bare | 3/3 | – | 3/3 | 3/3 | 974k | $0.99 |
| claude-code | claude-opus-5 | + skill | 3/3 | 1/3 | 3/3 | 3/3 | 999k | $1.03 |
| codex | gpt-5.6-terra | bare | 3/3 | – | 3/3 | 3/3 | 757k | $0.37 |
| codex | gpt-5.6-terra | + skill | 3/3 | 3/3 | 3/3 | 3/3 | 1,575k | $0.67 |

## Findings

1. **Saturated, but expensive.** 12/12, at 2–3× the tokens of B3/B9. Every trial read ZenML's installed source (`zenml/integrations/kubernetes/…`) to find `step_pod_service_account_name`, because neither the docs snapshot nor the skill documents step-pod service accounts. The task measures cost and method, not pass/fail, at this level.
2. **Every trial used `step_pod_service_account_name`** and every trial put the configuration in `config.yaml` (two Claude Code trials also touched code). The dead field `pod_settings.service_account_name` that the first reference used was chosen by no agent.
3. **Docs gap, actionable:** the Kubernetes orchestrator docs page should name `step_pod_service_account_name` / `service_account_name` and say that `pod_settings` carries no service account. The skill's Docker/Resource settings reference should mention it too. Re-run this task after the change to measure the token saving.
4. **Skill activation:** Claude Code 1/3 (the `pipeline-authoring` description mentions Docker/Resource settings, not Kubernetes); Codex 3/3. With the skill, Codex doubled its tokens for no change in outcome.
